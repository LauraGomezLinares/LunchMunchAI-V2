"""Build personalized recipe-generation context from persisted user data."""

from uuid import UUID

from sqlmodel import Session, select

from app.models.pantry import PantryItem
from app.models.user import User

EMPTY_PANTRY_PROMPT = (
    "El usuario no tiene ingredientes registrados. Sugiere una comida rápida "
    "de 5 ingredientes y elabora la lista de compras."
)


def build_recipe_context(session: Session, user_id: UUID) -> str:
    """Return the required system context for the user's pantry and allergies."""
    pantry_items = session.exec(
        select(PantryItem).where(PantryItem.usuario_id == user_id)
    ).all()
    if not pantry_items:
        return EMPTY_PANTRY_PROMPT

    user = session.get(User, user_id)
    allergies = user.alergias if user and isinstance(user.alergias, list) else []
    ingredient_names = [item.ingrediente for item in pantry_items]
    return (
        f"Ingredientes en despensa: [{', '.join(ingredient_names)}]. "
        f"Alergias prohibidas: [{', '.join(str(value) for value in allergies)}]. "
        "Debes crear una receta que use la despensa y JAMÁS incluya las alergias."
    )