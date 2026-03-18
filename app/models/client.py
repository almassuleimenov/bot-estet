from sqlalchemy import Column, Integer, String, Boolean, Text
from app.core.database import Base


class Client(Base):
    __tablename__ = "clients"

    id = Column(Integer, primary_key=True, index=True)
    chat_id = Column(
        String, unique=True, index=True
    )  # Номер WhatsApp (например, 77011234567@c.us)
    name = Column(String, nullable=True)
    context = Column(Text, default="")  # История диалога для ИИ
    is_bot_active = Column(
        Boolean, default=True
    )  # Флаг: общается ли бот или админ перехватил диалог
