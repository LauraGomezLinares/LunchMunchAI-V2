"""pantry item model - ingredientes de la despensa del usuario"""

from datetime import date, datetime
from typing import Optional 
from uuid import UUID, uuid4 

from sqlmodel import Field, SQLModel

class PantryItem(SQLModel, table=True):
    """ingrediente en la despensa digital el usuario"""
    __tablename__= "pantryitem"

    id: UUID = Field(default_factory= uuid4, primary_key=True)
    ingrediente: str = Field(max_length=120)
    cantidad: float = Field(gt=0)
    unidad: str = Field(max_length=20)
    fecha_caducidad: Optional[date] = None
    usuario_id: UUID = Field(foreign_key="user.id", index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)