"""Personalized recipe generation endpoint with deterministic safety checks."""

import asyncio

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from app.core.security import get_current_user
from app.db.session import get_session
from app.models.user import User
from app.schemas.recipes import RecipeGenerateRequest, RecipeRead
from app.services.ai_client import get_ai_provider
from app.services.allergen_filter import (
    AllergenDetectedException,
    validate_recipe_ingredients,
)
from app.services.context_builder import build_recipe_context

router = APIRouter(prefix="/api/v1/recipes", tags=["recipes"])
GENERATION_TIMEOUT_SECONDS = 15
MAX_GENERATION_ATTEMPTS = 3
TIMEOUT_MESSAGE = "El chef está pensando demasiado, intenta nuevamente."
UNSAFE_RECIPE_MESSAGE = (
    "No pudimos formular una receta completamente segura con tus ingientes actuales. "
    "Revisa tus restricciones."
)


@router.post("/generate", response_model=RecipeRead)
async def generate_recipe(
    payload: RecipeGenerateRequest | None = None,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> RecipeRead:
    """Generate a recipe and reject any result containing a user's allergens."""
    prompt = build_recipe_context(session, current_user.id)
    if payload and payload.excluir_receta:
        prompt = f"{prompt}\nExcluir la receta [{payload.excluir_receta}]."

    provider = get_ai_provider()
    allergies = current_user.alergias if isinstance(current_user.alergias, list) else []
    for _ in range(MAX_GENERATION_ATTEMPTS):
        try:
            recipe = await asyncio.wait_for(
                provider.generate_recipe(prompt), timeout=GENERATION_TIMEOUT_SECONDS
            )
        except asyncio.TimeoutError as exc:
            raise HTTPException(status_code=504, detail=TIMEOUT_MESSAGE) from exc
        try:
            validate_recipe_ingredients(recipe.ingredientes, allergies)
        except AllergenDetectedException as exc:
            prompt = (
                f"{prompt}\nLa receta anterior fue rechazada: no incluyas el alérgeno "
                f"{exc.allergen} ni el ingrediente {exc.ingredient}."
            )
            continue
        return recipe

    raise HTTPException(status_code=422, detail=UNSAFE_RECIPE_MESSAGE)