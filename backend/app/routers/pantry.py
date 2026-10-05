"""Pantry HTTP endpoints and inventory management."""

from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from app.core.security import get_current_user
from app.db.session import get_session
from app.models.pantry import PantryItem
from app.models.user import User
from app.schemas.pantry import PantryItemCreate, PantryItemRead, PantryItemUpdate

router = APIRouter(prefix="/api/v1/pantry", tags=["pantry"])


@router.get("/", response_model=List[PantryItemRead])
def list_pantry(
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> List[PantryItem]:
    """Retrieve pantry ingredients for the authenticated user ordered by expiration date."""
    query = (
        select(PantryItem)
        .where(PantryItem.usuario_id == current_user.id)
        .order_by(PantryItem.fecha_caducidad.asc().nulls_last())
    )
    return db.exec(query).all()


@router.post("/", response_model=PantryItemRead, status_code=status.HTTP_201_CREATED)
def create_pantry_item(
    data: PantryItemCreate,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> PantryItem:
    """Create and persist a new pantry ingredient for the authenticated user."""
    item = PantryItem(**data.model_dump(), usuario_id=current_user.id)
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
    """Partially or fully update an existing pantry ingredient owned by the authenticated user."""
    item = db.get(PantryItem, item_id)
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
    """Delete a pantry ingredient owned by the authenticated user."""
    item = db.get(PantryItem, item_id)
    if not item or item.usuario_id != current_user.id:
        raise HTTPException(status_code=404, detail="Ingrediente no encontrado")
    db.delete(item)
    db.commit()