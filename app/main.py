import asyncio
from datetime import datetime, timedelta
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

# Подключение к БД и модели
from app.core.database import (
    engine,
    async_session,
)  # <-- ВАЖНО: Убедись, что SessionLocal есть в database.py
from app.models import Base
from app.models.appointment import Appointment  # <-- Добавили для CRON
from app.models.doctor import Doctor
from app.models.settings import BotSettings
from app.services.whatsapp import (
    send_whatsapp_message,
)  # <-- Добавили для отправки СМС-напоминаний

# Твои роуты
from app.api.webhooks import router as webhooks_router
from app.api.admin_routes import router as admin_router
from app.api.instagram import router as instagram_router

# ==========================================
# ⏰ ФОНОВАЯ ЗАДАЧА: АВТО-НАПОМИНАНИЯ (CRON)
# ==========================================
scheduler = AsyncIOScheduler()


async def send_reminders():
    print("⏰ [CRON] Проверка заявок для напоминаний...")
    # Создаем временную сессию с базой данных для фоновой задачи
    async with async_session() as db:
        now = datetime.now()
        target_time = now + timedelta(hours=3)  # Ищем записи на ближайшие 3 часа

        # Ищем подтвержденные записи, у которых есть точное время, и которым еще не напомнили
        result = await db.execute(
            select(Appointment)
            .options(selectinload(Appointment.client))
            .where(
                Appointment.status == "confirmed",
                Appointment.scheduled_datetime != None,
                Appointment.is_reminded == False,
            )
        )
        appointments = result.scalars().all()

        for app in appointments:
            # Если время приема попадает в окно "от сейчас до +3 часов"
            if now < app.scheduled_datetime <= target_time:
                try:
                    time_str = app.scheduled_datetime.strftime("%H:%M")
                    msg = (
                        f"🌸 Здравствуйте! Напоминаем, сегодня в {time_str} ждем вас на прием в клинику «Эстет».\n\n"
                        f"Всё в силе? 🦷"
                    )

                    # Отправляем сообщение в WhatsApp
                    await send_whatsapp_message(app.client.chat_id, msg)

                    # Ставим галочку, что напомнили, чтобы не спамить
                    app.is_reminded = True
                    db.add(app)
                    print(
                        f"✅ Напоминание отправлено пациенту {app.client.chat_id} на {time_str}!"
                    )
                except Exception as e:
                    print(f"❌ Ошибка отправки напоминания: {e}")

        # Сохраняем изменения в базе
        await db.commit()


# ==========================================
# ЖИЗНЕННЫЙ ЦИКЛ СЕРВЕРА
# ==========================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🚀 Запуск Bot-Estet: подключаемся к PostgreSQL...")
    # Создаем все таблицы в базе данных (если их еще нет)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("✅ База данных и таблицы готовы!")

    # ⏰ ЗАПУСК ПЛАНИРОВЩИКА
    print("⏰ Включаем фоновые авто-напоминания...")
    # Проверять базу каждые 30 минут
    scheduler.add_job(send_reminders, "interval", minutes=30)
    scheduler.start()

    yield

    # Закрываем соединение и выключаем планировщик при остановке сервера
    scheduler.shutdown()
    await engine.dispose()
    print("🛑 Сервер остановлен. Соединение с БД закрыто.")


# ==========================================
# ИНИЦИАЛИЗАЦИЯ FASTAPI
# ==========================================
app = FastAPI(
    title="Bot Estet (AI Dental Assistant)",
    description="Микросервис для WhatsApp и админки расписания",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "*"
    ],  # В будущем для безопасности укажем тут адрес админки на Vercel
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(webhooks_router, tags=["Webhooks"])
app.include_router(admin_router, tags=["Admin API"])
app.include_router(instagram_router, tags=["Webhooks Instagram"])


@app.get("/")
async def root():
    return {"status": "ok", "message": "Bot-Estet API работает! CRON запущен! 🦷⏰"}
