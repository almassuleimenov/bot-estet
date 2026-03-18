from pydantic import BaseModel, ConfigDict
from typing import Optional


class TextMessageData(BaseModel):
    model_config = ConfigDict(extra="ignore")
    textMessage: str


class ExtendedTextMessageData(BaseModel):
    model_config = ConfigDict(extra="ignore")
    text: str


class FileMessageData(BaseModel):
    model_config = ConfigDict(extra="ignore")
    downloadUrl: str


class MessageData(BaseModel):
    model_config = ConfigDict(extra="ignore")
    typeMessage: str
    textMessageData: Optional[TextMessageData] = None
    extendedTextMessageData: Optional[ExtendedTextMessageData] = None
    fileMessageData: Optional[FileMessageData] = None


class SenderData(BaseModel):
    model_config = ConfigDict(extra="ignore")
    chatId: str
    sender: str = ""
    senderName: Optional[str] = None


class GreenApiWebhook(BaseModel):
    model_config = ConfigDict(extra="ignore")
    typeWebhook: str
    senderData: SenderData
    messageData: MessageData
