import os
import httpx
from dotenv import load_dotenv

load_dotenv()

GREEN_API_URL = os.getenv("GREEN_API_URL")
GREEN_API_ID = os.getenv("GREEN_API_ID")
GREEN_API_TOKEN = os.getenv("GREEN_API_TOKEN")

async def send_whatsapp_message(chat_id: str, message: str):
    """Отправляет сообщение через Green API"""
    if not all([GREEN_API_URL, GREEN_API_ID, GREEN_API_TOKEN]):
        print("❌ Ошибка: Не хватает ключей Green API в .env")
        return False

    url = f"{GREEN_API_URL}/waInstance{GREEN_API_ID}/sendMessage/{GREEN_API_TOKEN}"
    payload = {"chatId": chat_id, "message": message}

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            print(f"✅ Ответили в WhatsApp: {chat_id}")
            return True
        except Exception as e:
            print(f"❌ Ошибка отправки WhatsApp: {e}")
            return False

async def set_read_status(chat_id: str):
    """Ставит синие галочки (прочитано)"""
    url = f"{GREEN_API_URL}/waInstance{GREEN_API_ID}/readChat/{GREEN_API_TOKEN}"
    async with httpx.AsyncClient() as client:
        try:
            await client.post(url, json={"chatId": chat_id})
        except Exception as e:
            print(f"⚠️ Ошибка readChat: {e}")

async def set_typing_status(chat_id: str):
    """Включает статус 'Печатает...' (на несколько секунд)"""
    url = f"{GREEN_API_URL}/waInstance{GREEN_API_ID}/setChatTyping/{GREEN_API_TOKEN}"
    async with httpx.AsyncClient() as client:
        try:
            # Некоторые версии Green API принимают presence, другие просто chatId. Оставим надежный вариант:
            await client.post(url, json={"chatId": chat_id, "presence": "composing"})
        except Exception as e:
            print(f"⚠️ Ошибка setChatTyping: {e}")