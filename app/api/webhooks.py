import asyncio
import random
import json
from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.database import get_db
# Схему GreenApiWebhook мы убрали из параметров, чтобы FastAPI не блокировал кривые свайпы
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
async def handle_whatsapp_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    # 1. ЛОВИМ СЫРОЙ JSON (Бронебойный метод)
    try:
        raw_body = await request.json()
        print(f"\n🚀 ПОЙМАЛИ ВЕБХУК: {json.dumps(raw_body, ensure_ascii=False)}\n")
    except Exception as e:
        print(f"❌ Ошибка чтения JSON: {e}")
        return {"status": "error"}

    # 2. Проверяем, что это входящее сообщение
    type_webhook = raw_body.get("typeWebhook", "")
    if type_webhook != "incomingMessageReceived":
        return {"status": "ignored", "reason": "not an incoming message"}

    message_data = raw_body.get("messageData", {})
    msg_type = message_data.get("typeMessage", "")
    sender_data = raw_body.get("senderData", {})
    chat_id = sender_data.get("chatId", "")
    
    user_text = ""

    # 3. ДОСТАЕМ ТЕКСТ (Любой ценой)
    if msg_type == "textMessage":
        user_text = message_data.get("textMessageData", {}).get("textMessage", "")

    # 👇 ДОБАВИЛИ "quotedMessage" В ПРОВЕРКУ 👇
    elif msg_type in ["extendedTextMessage", "quotedMessage"]:
        # МАГИЯ ДЛЯ СВАЙПОВ И ОТВЕТОВ
        user_text = message_data.get("extendedTextMessageData", {}).get("text", "")
        if not user_text:
            print("⚠️ Свайп пришел без поля 'text'! Вытаскиваем все, что есть...")
            user_text = str(message_data.get("extendedTextMessageData", {}))

    elif msg_type == "audioMessage":
        audio_url = message_data.get("fileMessageData", {}).get("downloadUrl", "")
        if audio_url:
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

    # 4. Ищем клиента в базе
    result = await db.execute(select(Client).where(Client.chat_id == chat_id))
    client = result.scalars().first()

    if not client:
        client = Client(chat_id=chat_id)
        db.add(client)
        await db.commit()
        await db.refresh(client)

    # ==========================================
    # 🚨 НОВАЯ ЛОГИКА ИСТОРИИ (ДЛЯ LLAMA 3)
    # ==========================================
    # Пытаемся загрузить контекст как JSON-массив. 
    # Если там старый текст из прошлой версии, сбрасываем в [].
    try:
        messages_list = json.loads(client.context) if client.context else []
        if not isinstance(messages_list, list):
            messages_list = []
    except json.JSONDecodeError:
        messages_list = [] # Защита от старых строковых данных в БД

    # 5. ПРОВЕРКА КНОПКИ "СТОП" (Админ в деле)
    if not client.is_bot_active:
        print(f"🤫 Бот спит для клиента {chat_id}. Сохраняем сообщение для админа, но молчим.")
        # Сохраняем в новом формате
        messages_list.append({"role": "user", "content": user_text})
        client.context = json.dumps(messages_list[-6:], ensure_ascii=False)
        await db.commit()
        return {"status": "bot_is_sleeping"}

    # ==========================================
    # 🤖 ЧЕЛОВЕЧНОСТЬ: ПРОЧТЕНИЕ И ПЕЧАТЬ
    # ==========================================
    await set_read_status(chat_id)
    await asyncio.sleep(random.uniform(0.5, 1.5))
    await set_typing_status(chat_id)

    # 6. Отправляем текст ИИ (вместе с историей И ДИНАМИЧЕСКИМ ПРАЙСОМ)
    settings_result = await db.execute(select(BotSettings).where(BotSettings.id == 1))
    bot_settings = settings_result.scalars().first()
    current_price_list = (
        bot_settings.price_list
        if bot_settings
        else "Прайс-лист уточняется. Консультация 2000 тг."
    )

    # Вызываем нашу обновленную функцию!
    ai_response = await generate_dental_reply(
        user_text=user_text, 
        history=messages_list,  # Передаем массив словарей!
        dynamic_price_list=current_price_list
    )

    ai_reply_text = ai_response.get("reply", "Минуточку...")
    ai_action = ai_response.get("action", "none")
    suggested_service = ai_response.get("suggested_service")
    appointment_time = ai_response.get("appointment_time")

    # 7. Динамическая пауза (чем длиннее текст, тем дольше "печатаем")
    typing_delay = len(ai_reply_text) / 20.0 + random.uniform(0.5, 1.5)
    await asyncio.sleep(min(typing_delay, 5))

    # ==========================================
    # 8. ОБНОВЛЯЕМ ИСТОРИЮ ДИАЛОГА В ФОРМАТЕ JSON
    # ==========================================
    messages_list.append({"role": "user", "content": user_text})
    messages_list.append({"role": "assistant", "content": ai_reply_text})
    # Храним последние 6 сообщений (3 пары вопрос-ответ), чтобы не жрать токены
    client.context = json.dumps(messages_list[-6:], ensure_ascii=False)

    # 9. Заявка на прием (ТВОЙ КОД ОСТАЕТСЯ БЕЗ ИЗМЕНЕНИЙ)
    if ai_action in ["booking_requested", "time_agreed"] and appointment_time:
        
        ADMIN_WHATSAPP = "77772605712@c.us" # Твой номер

        result_app = await db.execute(
            select(Appointment)
            .where(Appointment.client_id == client.id)
            .where(Appointment.status.in_(["pending", "rescheduled"]))
            .order_by(Appointment.id.desc())
        )
        existing_app = result_app.scalars().first()

        clean_phone = chat_id.replace("@c.us", "")

        if existing_app:
            existing_app.appointment_time = appointment_time
            existing_app.status = "pending"
            print(f"🔄 Время обновлено на {appointment_time}.")

            admin_msg = (
                f"⚠️ *CRM Эстет: Обновление заявки!*\n\n"
                f"👤 Пациент: +{clean_phone}\n"
                f"🕒 Новое время: {appointment_time}\n\n"
                f"💻 Зайдите в админку!"
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
            print(f"🛎️ НОВАЯ ЗАЯВКА! Услуга: {suggested_service}, Время: {appointment_time}")

            admin_msg = (
                f"🚨 *CRM Эстет: НОВАЯ ЗАЯВКА!*\n\n"
                f"👤 Пациент: +{clean_phone}\n"
                f"🦷 Услуга: {suggested_service or 'Консультация'}\n"
                f"🕒 Время: {appointment_time}\n\n"
                f"💻 Зайдите в панель управления!"
            )
            await send_whatsapp_message(ADMIN_WHATSAPP, admin_msg)

    await db.commit()

    # 10. Отправляем готовый ответ
    await send_whatsapp_message(chat_id, ai_reply_text)

    return {"status": "ok"}