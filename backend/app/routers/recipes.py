"""endpoint de generacion de receta personalizada con comprobaciones de seguridad deterministas"""

import asyncio
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.core.security import get_current_user
from app.db.session import get_session
from app.models.favorite_recipe import FavoriteRecipe
from app.models.pantry import PantryItem
from app.models.user import User
from app.schemas.favorites import FavoriteCreate, FavoriteRead
from app.schemas.recipes import RecipeGenerateRequest, RecipeRead
from app.services.ai_client import NoLocalRecipeError, RecipeProviderError, get_ai_provider
from app.services.allergen_filter import (
    AllergenDetectedException,
    validate_recipe_ingredients,
)
from app.services.context_builder import build_recipe_context
from app.services.shopping_list import calcular_faltantes

router = APIRouter(prefix="/api/v1/recipes", tags=["recipes"])
GENERATION_TIMEOUT_SECONDS = 15
MAX_GENERATION_ATTEMPTS = 3
TIMEOUT_MESSAGE = "El chef está pensando demasiado, intenta nuevamente."
UNSAFE_RECIPE_MESSAGE = (
    "No pudimos formular una receta completamente segura con tus ingientes actuales. "
    "Revisa tus restricciones."
)


@router.post(
    "/favorites",
    response_model=FavoriteRead,
    status_code=status.HTTP_201_CREATED,
    summary="Guardar una receta favorita",
    responses={
        200: {"description": "La receta ya estaba guardada"},
        201: {"description": "Receta guardada"},
        401: {"description": "Autenticacion requerida"},
    },
)
def create_favorite(
    data: FavoriteCreate,
    response: Response,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> FavoriteRecipe:
    existing = session.exec(
        select(FavoriteRecipe).where(
            FavoriteRecipe.usuario_id == current_user.id,
            FavoriteRecipe.nombre == data.nombre,
        )
    ).first()
    if existing:
        response.status_code = status.HTTP_200_OK
        return existing

    favorite = FavoriteRecipe(
        usuario_id=current_user.id,
        nombre=data.nombre,
        receta=data.model_dump(mode="json"),
    )
    session.add(favorite)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        existing = session.exec(
            select(FavoriteRecipe).where(
                FavoriteRecipe.usuario_id == current_user.id,
                FavoriteRecipe.nombre == data.nombre,
            )
        ).first()
        if existing is None:
            raise
        response.status_code = status.HTTP_200_OK
        return existing
    session.refresh(favorite)
    return favorite


@router.get(
    "/favorites",
    response_model=list[FavoriteRead],
    summary="Listar las recetas favoritas",
    responses={401: {"description": "Autenticacion requerida"}},
)
def list_favorites(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> list[FavoriteRecipe]:
    return session.exec(
        select(FavoriteRecipe)
        .where(FavoriteRecipe.usuario_id == current_user.id)
        .order_by(FavoriteRecipe.fecha_guardado.desc(), FavoriteRecipe.id.desc())
    ).all()


@router.get(
    "/favorites/{favorite_id}",
    response_model=FavoriteRead,
    summary="Consultar una receta favorita guardada",
    responses={
        401: {"description": "Autenticacion requerida"},
        404: {"description": "Receta favorita no encontrada"},
    },
)
def get_favorite(
    favorite_id: UUID,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> FavoriteRecipe:
    favorite = session.get(FavoriteRecipe, favorite_id)
    if not favorite or favorite.usuario_id != current_user.id:
        raise HTTPException(status_code=404, detail="Receta favorita no encontrada")
    return favorite


@router.delete(
    "/favorites/{favorite_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Eliminar una receta favorita",
    responses={
        401: {"description": "Autenticacion requerida"},
        404: {"description": "Receta favorita no encontrada"},
    },
)
def delete_favorite(
    favorite_id: UUID,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Response:
    favorite = session.get(FavoriteRecipe, favorite_id)
    if not favorite or favorite.usuario_id != current_user.id:
        raise HTTPException(status_code=404, detail="Receta favorita no encontrada")
    session.delete(favorite)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/generate", response_model=RecipeRead)
async def generate_recipe(
    payload: RecipeGenerateRequest | None = None,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> RecipeRead:
    """
    genera una receta usando el proveedor seleccionado y cumple los checks de alergias.
    la llamada al proveedor tienen un limite de 15 sg, fallos de los alergenos deterministas se reintentan 3 veces
    la rpta del schema se mantiene igual independientemente si el proveedor es local, simulado o externo 
    """
    prompt = build_recipe_context(session, current_user.id)
    allergies = current_user.alergias if isinstance(current_user.alergias, list) else []
    if allergies and not prompt.startswith("Ingredientes en despensa:"):
        prompt = f"{prompt}\nAlergias prohibidas: [{', '.join(allergies)}]."
    if payload and payload.excluir_receta:
        prompt = f"{prompt}\nExcluir la receta [{payload.excluir_receta}]."

    provider = get_ai_provider()
    for _ in range(MAX_GENERATION_ATTEMPTS):
        try:
            recipe = await asyncio.wait_for(
                provider.generate_recipe(prompt), timeout=GENERATION_TIMEOUT_SECONDS
            )
        except asyncio.TimeoutError as exc:
            raise HTTPException(status_code=504, detail=TIMEOUT_MESSAGE) from exc
        except NoLocalRecipeError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except RecipeProviderError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        try:
            validate_recipe_ingredients(recipe.ingredientes, allergies)
        except AllergenDetectedException as exc:
            prompt = (
                f"{prompt}\nLa receta anterior fue rechazada: no incluyas el alérgeno "
                f"{exc.allergen} ni el ingrediente {exc.ingredient}."
            )
            continue
        pantry_items = session.exec(
            select(PantryItem).where(PantryItem.usuario_id == current_user.id)
        ).all()
        return recipe.model_copy(
            update={
                "ingredientes_faltantes": calcular_faltantes(
                    recipe.ingredientes, pantry_items
                )
            }
        )

    raise HTTPException(status_code=422, detail=UNSAFE_RECIPE_MESSAGE)