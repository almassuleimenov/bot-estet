import os
import tempfile
import httpx
from groq import AsyncGroq
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("GROQ_API_KEY")
client = AsyncGroq(api_key=api_key)


async def transcribe_audio_from_url(audio_url: str) -> str:
    """
    Скачивает аудио по ссылке и отправляет в Groq Whisper.
    Возвращает расшифрованный текст.
    """
    try:
        # 1. Скачиваем аудиофайл
        async with httpx.AsyncClient() as http_client:
            response = await http_client.get(audio_url)
            response.raise_for_status()

        # 2. Сохраняем во временный файл
        with tempfile.NamedTemporaryFile(delete=False, suffix=".ogg") as temp_audio:
            temp_audio.write(response.content)
            temp_filepath = temp_audio.name

        print(f"🎧 Аудио скачано. Отправляем в Whisper...")

        # 3. Отправляем в нейросеть для расшифровки
        with open(temp_filepath, "rb") as file:
            transcription = await client.audio.transcriptions.create(
                file=(temp_filepath, file.read()),
                model="whisper-large-v3",
                prompt="Это голосовое сообщение от пациента стоматологии. Язык может быть русский или казахский. Термины: кариес, пульпит, брекеты, удаление.",
            )

        # 4. Удаляем временный файл
        os.remove(temp_filepath)

        result_text = transcription.text.strip()
        print(f"📝 Расшифровано: {result_text}")
        return result_text

    except Exception as e:
        print(f"❌ Ошибка расшифровки аудио: {e}")
        # Если что-то пошло не так, не забываем удалить файл
        if "temp_filepath" in locals() and os.path.exists(temp_filepath):
            os.remove(temp_filepath)
        return ""
