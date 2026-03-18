from sqlalchemy import Column, Integer, String, Text
from app.core.database import Base


class Service(Base):
    __tablename__ = "services"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(
        String, nullable=False, unique=True
    )  # Название (например, "Отбеливание Zoom")
    category = Column(String, nullable=True)  # Категория ("Эстетика", "Хирургия")
    price = Column(
        String, nullable=True
    )  # Цена ("от 20 000 тг" - оставляем строкой для гибкости)
    description = Column(
        Text, nullable=True
    )  # Подробное описание услуги. ИИ будет читать это, чтобы консультировать клиента!
