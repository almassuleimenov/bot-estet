from sqlalchemy import Column, Integer, Text
from app.core.database import Base


class BotSettings(Base):
    __tablename__ = "bot_settings"

    id = Column(Integer, primary_key=True, index=True)
    price_list = Column(Text, nullable=True)
