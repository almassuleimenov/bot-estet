from pydantic import BaseModel, ConfigDict
from typing import Optional, List

# Схема для чтения данных о клиенте
class ClientResponse(BaseModel):
    id: int
    chat_id: str
    name: Optional[str]
    is_bot_active: bool

    model_config = ConfigDict(from_attributes=True) # Позволяет Pydantic читать данные из базы SQLAlchemy

# Схема для чтения записи на прием (Appointment)
class AppointmentResponse(BaseModel):
    id: int
    client_id: int
    doctor_id: Optional[int]
    service_name: Optional[str]
    appointment_time: Optional[str]
    status: str
    
    # Включаем вложенные данные клиента, чтобы в админке сразу был виден его номер
    client: Optional[ClientResponse] = None 

    model_config = ConfigDict(from_attributes=True)

# Схема для того, чтобы админ мог обновить статус (например, назначить врача)
class AppointmentUpdateRequest(BaseModel):
    doctor_id: Optional[int] = None
    status: Optional[str] = None # "confirmed", "rescheduled" и т.д.
    new_time: Optional[str] = None # Если админ предлагает другое время