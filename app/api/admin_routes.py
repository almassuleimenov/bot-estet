from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from typing import List
from pydantic import BaseModel
from app.models.settings import BotSettings
from app.core.database import get_db
from app.models.appointment import Appointment
from app.models.client import Client
from app.models.doctor import Doctor
from app.schemas.admin import AppointmentResponse, AppointmentUpdateRequest
from app.services.whatsapp import send_whatsapp_message

router = APIRouter(prefix="/api/admin", tags=["Admin API"])

@router.get("/appointments", response_model=List[AppointmentResponse])
async def get_appointments(db: AsyncSession = Depends(get_db)):
    """Отдает все заявки в Next.js админку (самые новые сверху)"""
    result = await db.execute(
        select(Appointment)
        .options(selectinload(Appointment.client)) # Подтягиваем данные клиента (номер телефона)
        .order_by(Appointment.id.desc())
    )
    return result.scalars().all()

@router.put("/appointments/{appointment_id}")
async def update_appointment(
    appointment_id: int, 
    update_data: AppointmentUpdateRequest, 
    db: AsyncSession = Depends(get_db)
):
    """Next.js присылает сюда статус 'confirmed' и ID врача"""
    result = await db.execute(
        select(Appointment)
        .options(selectinload(Appointment.client))
        .where(Appointment.id == appointment_id)
    )
    appointment = result.scalars().first()

    if not appointment:
        raise HTTPException(status_code=404, detail="Заявка не найдена")

    # 1. Обновляем данные в БД
    if update_data.doctor_id:
        appointment.doctor_id = update_data.doctor_id
    if update_data.status:
        appointment.status = update_data.status

    # 2. ЕСЛИ ПОДТВЕРДИЛИ -> Пишем клиенту радостную новость
    # 2. ЕСЛИ ПОДТВЕРДИЛИ -> Пишем клиенту радостную новость с 2GIS
    if update_data.status == "confirmed":
        msg = (
            f"🎉 Отличные новости! Ваша запись на *{appointment.appointment_time}* подтверждена.\n\n"
            f"Ждем вас в стоматологии «Эстет»! 🦷\n"
            f"🗺️ Построить маршрут в 2GIS: https://2gis.kz/turkestan/geo/70000001090123854"
        )
        await send_whatsapp_message(appointment.client.chat_id, msg)

    # 3. ЕСЛИ ВРЕМЯ ЗАНЯТО -> Предлагаем новое (гибкий текст от админа)
    elif update_data.status == "rescheduled" and update_data.new_time:
        msg = f"🌸 Здравствуйте! Администратор проверил расписание:\n\n{update_data.new_time}"
        await send_whatsapp_message(appointment.client.chat_id, msg)
        appointment.appointment_time = update_data.new_time
    await db.commit()
    return {"status": "success", "message": "Заявка обновлена, клиент уведомлен!"}
@router.put("/clients/{client_id}/toggle-bot")
async def toggle_bot_status(client_id: int, db: AsyncSession = Depends(get_db)):
    """Включает или выключает ИИ для конкретного клиента"""
    result = await db.execute(select(Client).where(Client.id == client_id))
    client = result.scalars().first()
    
    if not client:
        raise HTTPException(status_code=404, detail="Клиент не найден")
        
    client.is_bot_active = not client.is_bot_active # Меняем статус на противоположный
    await db.commit()
    
    status_text = "включен" if client.is_bot_active else "отключен"
    return {"status": "success", "message": f"Бот {status_text} для клиента", "is_bot_active": client.is_bot_active}
# --- НАСТРОЙКИ ИИ ---

class SettingsUpdateRequest(BaseModel):
    price_list: str

@router.get("/settings")
async def get_settings(db: AsyncSession = Depends(get_db)):
    """Отдает текущий прайс-лист в React"""
    result = await db.execute(select(BotSettings).where(BotSettings.id == 1))
    settings = result.scalars().first()
    
    if not settings:
        return {"price_list": ""}
    return {"price_list": settings.price_list}

@router.put("/settings")
async def update_settings(data: SettingsUpdateRequest, db: AsyncSession = Depends(get_db)):
    """Сохраняет новый прайс-лист от админа"""
    result = await db.execute(select(BotSettings).where(BotSettings.id == 1))
    settings = result.scalars().first()
    
    if not settings:
        settings = BotSettings(id=1, price_list=data.price_list)
        db.add(settings)
    else:
        settings.price_list = data.price_list
        
    await db.commit()
    return {"status": "success", "message": "Настройки ИИ обновлены!"}