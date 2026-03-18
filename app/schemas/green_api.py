from pydantic import BaseModel
from typing import Optional

# Вложенные структуры для сообщения
class TextMessageData(BaseModel):
    textMessage: str
class ExtendedTextMessageData(BaseModel): # <-- ДОБАВИЛИ ЭТО!
    text: str
    
class FileMessageData(BaseModel):
    downloadUrl: str

class MessageData(BaseModel):
    typeMessage: str
    textMessageData: Optional[TextMessageData] = None
    fileMessageData: Optional[FileMessageData] = None

class SenderData(BaseModel):
    chatId: str

# Главная схема входящего вебхука от Green API
class GreenApiWebhook(BaseModel):
    typeWebhook: str
    senderData: SenderData
    messageData: MessageData