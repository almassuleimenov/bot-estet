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
    elif msg_type == "audioMessage":
        audio_url = webhook.messageData.fileMessageData.downloadUrl
        user_text = await transcribe_audio_from_url(audio_url)
        if not user_text:
            await send_whatsapp_message(chat_id, "Извините, я не смогла разобрать голосовое сообщение. Напишите, пожалуйста, текстом 🌸")
            return {"status": "audio_failed"}
    else:
        return {"status": "ignored", "reason": "unsupported message type"}

    # 3. Ищем клиента в базе
    result = await db.execute(select(Client).where(Client.chat_id == chat_id))
    client = result.scalars().first()

    if not client:
        client = Client(chat_id=chat_id)
        db.add(client)
        await db.commit()
        await db.refresh(client)

    # 4. 🚨 ПРОВЕРКА КНОПКИ "СТОП" 🚨
    if not client.is_bot_active:
        print(f"🤫 Бот спит для клиента {chat_id}. Ждем ответа админа.")
        return {"status": "bot_is_sleeping"}

    # ==========================================
    # 🤖 ЧЕЛОВЕЧНОСТЬ: ПРОЧТЕНИЕ И ПЕЧАТЬ
    # ==========================================
    
    # Делаем вид, что админ взял телефон и прочитал сообщение (Синие галочки)
    await set_read_status(chat_id)
    await asyncio.sleep(random.uniform(0.5, 1.5)) # Пауза перед началом набора текста

    # Включаем плашку "печатает..."
    await set_typing_status(chat_id)

    # 5. Отправляем текст ИИ (вместе с историей). Это займет 1-3 секунды (идеально совпадает со временем "печати")
    ai_response = await generate_dental_reply(user_text, client.context)
    ai_reply_text = ai_response.get("reply", "Минуточку...")
    ai_action = ai_response.get("action", "none")
    suggested_service = ai_response.get("suggested_service")
    appointment_time = ai_response.get("appointment_time")

    # 6. Динамическая пауза (чем длиннее текст придумал ИИ, тем дольше мы "печатаем")
    # Допустим, человек печатает 20 символов в секунду
    typing_delay = len(ai_reply_text) / 20.0 + random.uniform(0.5, 1.5)
    await asyncio.sleep(min(typing_delay, 5)) # Максимум 5 секунд, чтобы клиент не устал ждать

    # 7. Обновляем историю диалога
    new_context = f"{client.context}\nКлиент: {user_text}\nЭстет: {ai_reply_text}"
    client.context = new_context[-2000:] 

    # 8. Заявка на прием
    if ai_action == "booking_requested" and appointment_time:
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