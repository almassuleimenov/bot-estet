from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.core.database import engine
from app.models import Base  # Импортируем Base, который уже знает обо всех таблицах
from app.api.webhooks import router as webhooks_router
from app.api.admin_routes import router as admin_router # <-- Добавили импорт
from fastapi.middleware.cors import CORSMiddleware
from app.api.instagram import router as instagram_router 
from app.models.doctor import Doctor          # <-- ВАЖНО!
from app.models.settings import BotSettings # <-- Добавили импорт

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🚀 Запуск Bot-Estet: подключаемся к PostgreSQL...")
    # Создаем все таблицы в базе данных (если их еще нет)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("✅ База данных и таблицы готовы!")
    yield
    # Закрываем соединение при выключении сервера
    await engine.dispose()
    print("🛑 Сервер остановлен. Соединение с БД закрыто.")

app = FastAPI(
    title="Bot Estet (AI Dental Assistant)",
    description="Микросервис для WhatsApp и админки расписания",
    version="1.0.0",
    lifespan=lifespan
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # В будущем для безопасности укажем тут адрес админки на Vercel
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(webhooks_router, tags=["Webhooks"])
app.include_router(admin_router, tags=["Admin API"]) 
app.include_router(instagram_router, tags=["Webhooks Instagram"]) 

@app.get("/")
async def root():
    return {"status": "ok", "message": "Bot-Estet API работает! 🦷"}