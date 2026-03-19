from sqlalchemy import Column, Integer, String, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from app.core.database import Base


class Appointment(Base):
    __tablename__ = "appointments"

    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False)
    doctor_id = Column(
        Integer, ForeignKey("doctors.id"), nullable=True
    )  # Может быть пустым, пока админ не назначит врача

    service_name = Column(
        String, nullable=True
    )  # Какая услуга нужна (Отбеливание, Консультация)
    appointment_time = Column(
        String, nullable=True
    )  # Желаемое время текстом (например, "Завтра в 15:00")
    
    # ⏰ НОВАЯ КОЛОНКА ДЛЯ АВТО-НАПОМИНАНИЙ (Строгое машинное время)
    scheduled_datetime = Column(DateTime, nullable=True)

    # Статусы: pending (ждет админа), confirmed (бинго!), rescheduled (админ предложил другое время), completed (завершено)
    status = Column(String, default="pending")

    # Связи для удобного получения данных
    client = relationship("Client", backref="appointments")
    doctor = relationship("Doctor", backref="appointments")