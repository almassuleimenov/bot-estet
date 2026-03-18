from sqlalchemy import Column, Integer, String, Boolean
from app.core.database import Base

class Doctor(Base):
    __tablename__ = "doctors"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False) # Имя врача (например, Дархан)
    phone = Column(String, nullable=True)
    specialty = Column(String, nullable=True) # Специализация (Ортодонт, Хирург)
    is_active = Column(Boolean, default=True) # Работает ли сейчас врач