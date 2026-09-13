"""pantry schemas - validacion de entrada/salida"""

from datetime import date, datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict

class PantryItemCreate(BaseModel):
    ingrediente: str = Field(min_length=1, max_length=120)
    cantidad: float = Field(gt=0)
    unidad: str = Field(min_length=1, max_length=20)
    fecha_caducidad: Optional[date] = None

class PantryItemUpdate(BaseModel):
    ingrediente: Optional[str] = Field(default= None, min_length=1, max_length=120)
    cantidad: Optional[float] = Field(default=None, gt=0)
    unidad: Optional[str] = Field(default=None, min_length=1, max_length=20)
    fecha_caducidad: Optional[date] = None

class PantryItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    ingrediente: str
    cantidad: float
    unidad: str
    fecha_caducidad: Optional[date]
    created_at: datetime

    #class Config:
        #from_attributes= True