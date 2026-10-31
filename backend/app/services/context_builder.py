"""construye una generacion de recetas personalizadas desde la info del usuario persistida"""

from uuid import UUID

from sqlmodel import Session, select

from app.models.pantry import PantryItem
from app.models.user import User
from app.services.expiry import obtener_por_vencer

EMPTY_PANTRY_PROMPT = (
    "El usuario no tiene ingredientes registrados. Sugiere una comida rápida "
    "de 5 ingredientes y elabora la lista de compras."
)


def build_recipe_context(session: Session, user_id: UUID) -> str:
    """
    construye el contexto estable para el proveedor desde la info persistida del usuario
    filas de la despensa son delimitadas desde `usuario_id`, con una despensa no vacia el resultado incluye nombres
    de la despensa y la lista de las alergias del usuario, cuando esta vacia retorna el fallback del sprint 02, el ruter de
    recetas separadamente añade alergias por separado para que el proveedor aun reciba las restricciones de seguridad.
    """
    pantry_items = session.exec(
        select(PantryItem).where(PantryItem.usuario_id == user_id)
    ).all()
    user = session.get(User, user_id)
    allergies = user.alergias if user and isinstance(user.alergias, list) else []
    if not pantry_items:
        return EMPTY_PANTRY_PROMPT

    ingredient_names = [item.ingrediente for item in pantry_items]
    context = (
        f"Ingredientes en despensa: [{', '.join(ingredient_names)}]. "
        f"Alergias prohibidas: [{', '.join(str(value) for value in allergies)}]. "
        "Debes crear una receta que use la despensa y JAMÁS incluya las alergias."
    )
    expiring_names = [
        item.ingrediente for item in obtener_por_vencer(pantry_items)
    ]
    if expiring_names:
        context += (
            f"\nIngredientes próximos a vencer (priorízalos): "
            f"[{', '.join(expiring_names)}]. Úsalos cuando sea posible."
        )
    return context