"""pantry router - endpoints"""

from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from app.db.session import get_session
from app.models.pantry import PantryItem
from app.models.user import User
from app.schemas.pantry import PantryItemCreate, PantryItemRead, PantryItemUpdate
from app.core.security import get_current_user

router= APIRouter(prefix="/api/v1/pantry", tags=["pantry"])

@router.get("/", response_model=List[PantryItemRead])
#ordenadopor fecha de caducidad, vere si lo cambio a normal pero creo q es lo mejor por ahora
def list_pantry(
    db:Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> List[PantryItem]:
    query=(select(PantryItem).where(PantryItem.usuario_id == current_user.id)
           .order_by(PantryItem.fecha_caducidad.asc().nulls_last()))
    return db.exec(query).all()


@router.post("/", response_model=PantryItemRead, status_code=status.HTTP_201_CREATED)
def create_pantry_item(
    data: PantryItemCreate,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> PantryItem: 
    item= PantryItem(**data.model_dump(), usuario_id=current_user.id)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.put("/{item_id}", response_model=PantryItemRead)
def update_pantry_item(
    item_id: UUID,
    data: PantryItemUpdate,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> PantryItem:
    item= db.get(PantryItem, item_id)
    if not item or item.usuario_id != current_user.id:
        raise HTTPException(status_code=404, detail="Ingrediente no encontrado")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(item, key, value)

    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_pantry_item(
    item_id: UUID,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> None:
    item = db.get(PantryItem, item_id)
    if not item or item.usuario_id != current_user.id:
        raise HTTPException(status_code=404, detail="Ingrediente no encontrado")
    db.delete(item)
    db.commit()