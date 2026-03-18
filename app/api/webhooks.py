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
# ВАЖНО: Импортируем новые функции!
from app.services.whatsapp import send_whatsapp_message, set_read_status, set_typing_status 
from app.services.audio import transcribe_audio_from_url
from app.models.settings import BotSettings 

router = APIRouter()

@router.post("/whatsapp-webhook")
async def handle_whatsapp_webhook(
    webhook: GreenApiWebhook, 
    db: AsyncSession = Depends(get_db)
):
    # 1. Проверяем, что это входящее сообщение
    if webhook.typeWebhook != "incomingMessageReceived":
        return {"status": "ignored", "reason": "not an incoming message"}

    msg_type = webhook.messageData.typeMessage
    chat_id = webhook.senderData.chatId
    user_text = ""

    # 2. Достаем текст или скачиваем аудио
    if msg_type == "textMessage":
        user_text = webhook.messageData.textMessageData.textMessage
    elif msg_type == "extendedTextMessage": # <-- ОБРАБАТЫВАЕМ СВАЙПЫ-ОТВЕТЫ!
        user_text = webhook.messageData.extendedTextMessageData.text
    elif msg_type == "audioMessage":
        audio_url = webhook.messageData.fileMessageData.downloadUrl
        user_text = await transcribe_audio_from_url(audio_url)
        if not user_text:
            await send_whatsapp_message(chat_id, "Извините, я не смогла разобрать голосовое сообщение. Напишите, пожалуйста, текстом 🌸")
            return {"status": "audio_failed"}
    else:
        # Игнорируем картинки, стикеры, локации и т.д.
        return {"status": "ignored", "reason": f"unsupported message type: {msg_type}"}

    # 3. Ищем клиента в базе
    result = await db.execute(select(Client).where(Client.chat_id == chat_id))
    client = result.scalars().first()

    if not client:
        client = Client(chat_id=chat_id)
        db.add(client)
        await db.commit()
        await db.refresh(client)

    # Подготавливаем текущую историю
    messages_list = client.context.split('\n') if client.context else []
    messages_list = [m for m in messages_list if m.strip()]

    # 4. 🚨 ПРОВЕРКА КНОПКИ "СТОП" (ФИКС) 🚨
    if not client.is_bot_active:
        print(f"🤫 Бот спит для клиента {chat_id}. Сохраняем сообщение для админа, но молчим.")
        # Сохраняем то, что написал клиент, чтобы админ видел это в CRM
        messages_list.append(f"Клиент: {user_text}")
        client.context = '\n'.join(messages_list[-6:]) # Оставляем только 6 последних
        
        await db.commit() # Сохраняем в БД
        return {"status": "bot_is_sleeping"}

    # ==========================================
    # 🤖 ЧЕЛОВЕЧНОСТЬ: ПРОЧТЕНИЕ И ПЕЧАТЬ
    # ==========================================
    
    # Делаем вид, что админ взял телефон и прочитал сообщение (Синие галочки)
    await set_read_status(chat_id)
    await asyncio.sleep(random.uniform(0.5, 1.5)) # Пауза перед началом набора текста

    # Включаем плашку "печатает..."
    await set_typing_status(chat_id)

    # 5. Отправляем текст ИИ (вместе с историей И ДИНАМИЧЕСКИМ ПРАЙСОМ)
    
    # Сначала достаем прайс из БД
    settings_result = await db.execute(select(BotSettings).where(BotSettings.id == 1))
    bot_settings = settings_result.scalars().first()
    current_price_list = bot_settings.price_list if bot_settings else "Прайс-лист уточняется. Консультация 2000 тг."

    # Передаем текст пользователя, историю и НАШ ПРАЙС в функцию ИИ
    ai_response = await generate_dental_reply(user_text, client.context, current_price_list)
    
    ai_reply_text = ai_response.get("reply", "Минуточку...")
    ai_action = ai_response.get("action", "none")
    suggested_service = ai_response.get("suggested_service")
    appointment_time = ai_response.get("appointment_time")

    # 6. Динамическая пауза (чем длиннее текст, тем дольше "печатаем")
    typing_delay = len(ai_reply_text) / 20.0 + random.uniform(0.5, 1.5)
    await asyncio.sleep(min(typing_delay, 5))

    # 7. Обновляем историю диалога (ФИКС ГАЛЛЮЦИНАЦИЙ)
    messages_list.append(f"Клиент: {user_text}")
    messages_list.append(f"Эстет: {ai_reply_text}")
    
    # ✂️ Оставляем ТОЛЬКО 6 последних сообщений (3 вопроса, 3 ответа), чтобы ИИ не тупил
    client.context = '\n'.join(messages_list[-6:]) 

    # 8. Заявка на прием
    if ai_action in ["booking_requested", "time_agreed"] and appointment_time:
        # Ищем, есть ли у клиента уже активная заявка (которую мы переносили или которая висит)
        result_app = await db.execute(
            select(Appointment)
            .where(Appointment.client_id == client.id)
            .where(Appointment.status.in_(["pending", "rescheduled"]))
            .order_by(Appointment.id.desc())
        )
        existing_app = result_app.scalars().first()

        if existing_app:
            # Заявка уже есть. Обновляем время
            existing_app.appointment_time = appointment_time
            # Если клиент согласился на предложенное время -> Автоматически подтверждаем!
            if ai_action == "time_agreed" or existing_app.status == "rescheduled":
                existing_app.status = "confirmed"
                print(f"✅ Клиент согласился на время {appointment_time}. Статус -> confirmed")
            else:
                existing_app.status = "pending"
        else:
            # Создаем новую заявку
            new_appointment = Appointment(
                client_id=client.id,
                service_name=suggested_service,
                appointment_time=appointment_time,
                status="pending"
            )
            db.add(new_appointment)
            print(f"🛎️ НОВАЯ ЗАЯВКА! Услуга: {suggested_service}, Время: {appointment_time}")

    await db.commit()
    # 9. И только теперь отправляем готовый ответ
    await send_whatsapp_message(chat_id, ai_reply_text)

    return {"status": "ok"}