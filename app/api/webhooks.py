import asyncio
import random
from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.database import get_db
from app.schemas.green_api import GreenApiWebhook
from app.models.client import Client
from app.models.appointment import Appointment
from app.services.ai import generate_dental_reply
from app.services.whatsapp import (
    send_whatsapp_message,
    set_read_status,
    set_typing_status,
)
from app.services.audio import transcribe_audio_from_url
from app.models.settings import BotSettings

router = APIRouter()


@router.post("/whatsapp-webhook")
async def handle_whatsapp_webhook(
    webhook: GreenApiWebhook, db: AsyncSession = Depends(get_db)
):
    # 1. Проверяем, что это входящее сообщение
    if webhook.typeWebhook != "incomingMessageReceived":
        return {"status": "ignored", "reason": "not an incoming message"}

    msg_type = webhook.messageData.typeMessage
    chat_id = webhook.senderData.chatId
    user_text = ""

    # 2. БЕЗОПАСНО Достаем текст или скачиваем аудио
    if msg_type == "textMessage" and webhook.messageData.textMessageData:
        user_text = webhook.messageData.textMessageData.textMessage
    elif (
        msg_type == "extendedTextMessage"
        and webhook.messageData.extendedTextMessageData
    ):
        # <-- ВОТ ОНА, МАГИЯ ДЛЯ СВАЙПОВ!
        user_text = webhook.messageData.extendedTextMessageData.text
    elif msg_type == "audioMessage" and webhook.messageData.fileMessageData:
        audio_url = webhook.messageData.fileMessageData.downloadUrl
        user_text = await transcribe_audio_from_url(audio_url)
        if not user_text:
            await send_whatsapp_message(
                chat_id,
                "Извините, я не смогла разобрать голосовое сообщение. Напишите, пожалуйста, текстом 🌸",
            )
            return {"status": "audio_failed"}
    else:
        # Игнорируем картинки, стикеры, локации и т.д.
        return {"status": "ignored", "reason": f"unsupported message type: {msg_type}"}

    # Если вдруг текст оказался пустым
    if not user_text:
        return {"status": "ignored", "reason": "empty text"}

    # 3. Ищем клиента в базе
    result = await db.execute(select(Client).where(Client.chat_id == chat_id))
    client = result.scalars().first()

    if not client:
        client = Client(chat_id=chat_id)
        db.add(client)
        await db.commit()
        await db.refresh(client)

    # Подготавливаем текущую историю
    messages_list = client.context.split("\n") if client.context else []
    messages_list = [m for m in messages_list if m.strip()]

    # 4. ПРОВЕРКА КНОПКИ "СТОП" (Админ в деле)
    if not client.is_bot_active:
        print(
            f"🤫 Бот спит для клиента {chat_id}. Сохраняем сообщение для админа, но молчим."
        )
        messages_list.append(f"Клиент: {user_text}")
        client.context = "\n".join(messages_list[-6:])
        await db.commit()
        return {"status": "bot_is_sleeping"}

    # ==========================================
    # 🤖 ЧЕЛОВЕЧНОСТЬ: ПРОЧТЕНИЕ И ПЕЧАТЬ
    # ==========================================
    await set_read_status(chat_id)
    await asyncio.sleep(random.uniform(0.5, 1.5))
    await set_typing_status(chat_id)

    # 5. Отправляем текст ИИ (вместе с историей И ДИНАМИЧЕСКИМ ПРАЙСОМ)
    settings_result = await db.execute(select(BotSettings).where(BotSettings.id == 1))
    bot_settings = settings_result.scalars().first()
    current_price_list = (
        bot_settings.price_list
        if bot_settings
        else "Прайс-лист уточняется. Консультация 2000 тг."
    )

    ai_response = await generate_dental_reply(
        user_text, client.context, current_price_list
    )

    ai_reply_text = ai_response.get("reply", "Минуточку...")
    ai_action = ai_response.get("action", "none")
    suggested_service = ai_response.get("suggested_service")
    appointment_time = ai_response.get("appointment_time")

    # 6. Динамическая пауза (чем длиннее текст, тем дольше "печатаем")
    typing_delay = len(ai_reply_text) / 20.0 + random.uniform(0.5, 1.5)
    await asyncio.sleep(min(typing_delay, 5))

    # 7. Обновляем историю диалога
    messages_list.append(f"Клиент: {user_text}")
    messages_list.append(f"Эстет: {ai_reply_text}")
    client.context = "\n".join(messages_list[-6:])

    # 8. Заявка на прием
    if ai_action in ["booking_requested", "time_agreed"] and appointment_time:

        # 🚨 НОМЕР АДМИНА ДЛЯ УВЕДОМЛЕНИЙ (Впиши сюда свой номер с @c.us)
        ADMIN_WHATSAPP = "77753159203@c.us"

        result_app = await db.execute(
            select(Appointment)
            .where(Appointment.client_id == client.id)
            .where(Appointment.status.in_(["pending", "rescheduled"]))
            .order_by(Appointment.id.desc())
        )
        existing_app = result_app.scalars().first()

        # Маскируем номер для красоты в уведомлении
        clean_phone = chat_id.replace("@c.us", "")

        if existing_app:
            existing_app.appointment_time = appointment_time
            existing_app.status = "pending"
            print(
                f"🔄 Время обновлено на {appointment_time}. Карточка ждет назначения врача админом (pending)."
            )

            # --- ОТПРАВЛЯЕМ ПУШ АДМИНУ (Обновление времени) ---
            admin_msg = (
                f"⚠️ *CRM Эстет: Обновление заявки!*\n\n"
                f"👤 Пациент: +{clean_phone}\n"
                f"🕒 Новое время: {appointment_time}\n\n"
                f"💻 Зайдите в админку, чтобы подтвердить и назначить врача!"
            )
            await send_whatsapp_message(ADMIN_WHATSAPP, admin_msg)

        else:
            new_appointment = Appointment(
                client_id=client.id,
                service_name=suggested_service,
                appointment_time=appointment_time,
                status="pending",
            )
            db.add(new_appointment)
            print(
                f"🛎️ НОВАЯ ЗАЯВКА! Услуга: {suggested_service}, Время: {appointment_time}"
            )

            # --- ОТПРАВЛЯЕМ ПУШ АДМИНУ (Новая заявка) ---
            admin_msg = (
                f"🚨 *CRM Эстет: НОВАЯ ЗАЯВКА!*\n\n"
                f"👤 Пациент: +{clean_phone}\n"
                f"🦷 Услуга: {suggested_service or 'Консультация'}\n"
                f"🕒 Время: {appointment_time}\n\n"
                f"💻 Зайдите в панель управления, карточка уже в 'Запросах'!"
            )
            await send_whatsapp_message(ADMIN_WHATSAPP, admin_msg)

    await db.commit()

    # 9. Отправляем готовый ответ
    await send_whatsapp_message(chat_id, ai_reply_text)

    return {"status": "ok"}
