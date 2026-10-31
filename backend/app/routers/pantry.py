"""Rutas de gestion de la despensa."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from app.db.session import get_session
from app.models.pantry import PantryItem
from app.models.user import User
from app.schemas.pantry import PantryItemCreate, PantryItemRead, PantryItemUpdate
from app.core.security import get_current_user
from app.services.expiry import (
    clasificar_vencimiento,
    ordenar_por_vencimiento,
)

router = APIRouter(prefix="/api/v1/pantry", tags=["pantry"])


def _read_item(item: PantryItem) -> PantryItemRead:
    estado, dias = clasificar_vencimiento(item.fecha_caducidad)
    return PantryItemRead(
        id=item.id,
        ingrediente=item.ingrediente,
        cantidad=item.cantidad,
        unidad=item.unidad,
        fecha_caducidad=item.fecha_caducidad,
        created_at=item.created_at,
        estado_vencimiento=estado,
        dias_para_vencer=dias,
    )


@router.get(
    "/",
    response_model=list[PantryItemRead],
    summary="Listar la despensa ordenada por vencimiento",
)
def list_pantry(
    db:Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> list[PantryItemRead]:
    query = select(PantryItem).where(PantryItem.usuario_id == current_user.id)
    items = ordenar_por_vencimiento(db.exec(query).all())
    return [_read_item(item) for item in items]


@router.get(
    "/expiring-summary",
    response_model=dict[str, int],
    summary="Contar ingredientes vencidos y proximos a vencer",
    responses={401: {"description": "Autenticacion requerida"}},
)
def expiring_summary(
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> dict[str, int]:
    items = db.exec(
        select(PantryItem).where(PantryItem.usuario_id == current_user.id)
    ).all()
    estados = [
        clasificar_vencimiento(item.fecha_caducidad)[0] for item in items
    ]
    return {
        "por_vencer": estados.count("por_vencer"),
        "vencidos": estados.count("vencido"),
    }


@router.post(
    "/",
    response_model=PantryItemRead,
    status_code=status.HTTP_201_CREATED,
    summary="Agregar un ingrediente a la despensa",
)
def create_pantry_item(
    data: PantryItemCreate,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> PantryItemRead:
    item = PantryItem(**data.model_dump(), usuario_id=current_user.id)
    db.add(item)
    db.commit()
    db.refresh(item)
    return _read_item(item)


@router.put(
    "/{item_id}",
    response_model=PantryItemRead,
    summary="Actualizar un ingrediente de la despensa",
    responses={404: {"description": "Ingrediente no encontrado"}},
)
def update_pantry_item(
    item_id: UUID,
    data: PantryItemUpdate,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> PantryItemRead:
    item = db.get(PantryItem, item_id)
    if not item or item.usuario_id != current_user.id:
        raise HTTPException(status_code=404, detail="Ingrediente no encontrado")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(item, key, value)

    db.add(item)
    db.commit()
    db.refresh(item)
    return _read_item(item)


@router.delete(
    "/{item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Eliminar un ingrediente de la despensa",
    responses={404: {"description": "Ingrediente no encontrado"}},
)
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