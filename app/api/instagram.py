from fastapi import APIRouter, Request, Response

router = APIRouter(prefix="/api/instagram", tags=["Instagram Webhooks"])

# Это наш секретный пароль. Можешь придумать любой, но мы будем использовать этот:
VERIFY_TOKEN = "estet_super_secret_token_123"

@router.get("/webhook")
async def verify_instagram_webhook(request: Request):
    """
    ЭТУ ФУНКЦИЮ FACEBOOK ДЕРГАЕТ ТОЛЬКО ОДИН РАЗ ДЛЯ ПРОВЕРКИ ССЫЛКИ.
    Он присылает нам hub.verify_token и hub.challenge.
    """
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")

    if mode == "subscribe" and token == VERIFY_TOKEN:
        print("✅ Вебхук Instagram успешно подтвержден Facebook'ом!")
        # Facebook требует вернуть именно этот challenge как обычный текст
        return Response(content=challenge, media_type="text/plain")
    else:
        print("❌ Ошибка подтверждения Instagram вебхука!")
        return Response(content="Forbidden", status_code=403)


@router.post("/webhook")
async def handle_instagram_messages(request: Request):
    """
    Сюда будут падать реальные сообщения из Директа (после подтверждения).
    Логику ИИ мы добавим сюда чуть позже.
    """
    try:
        data = await request.json()
        print("📩 Пришел вебхук от Instagram:", data)
        return {"status": "ok"}
    except Exception as e:
        print(f"Ошибка парсинга инсты: {e}")
        return {"status": "error"}