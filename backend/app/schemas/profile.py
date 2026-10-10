"""contratos de request y rpta para campos editables en el perfil de usuario"""

from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator

ALLOWED_ALLERGIES = (
    "Gluten",
    "Lácteos",
    "Huevos",
    "Maní",
    "Frutos secos",
    "Soya",
    "Pescado",
    "Mariscos",
)


class ProfileUpdate(BaseModel):
    """
    actu parcial del perfil conteniendo solamente la matriz de alergias
    cada valor debe coincidir con el catalogo publico; fastapi retorna http 422 para las
    etiquetas desconocidas.
    """

    alergias: list[str]

    @field_validator("alergias")
    @classmethod
    def validate_allergies(cls, value: list[str]) -> list[str]:
        invalid = [allergy for allergy in value if allergy not in ALLOWED_ALLERGIES]
        if invalid:
            allowed = ", ".join(ALLOWED_ALLERGIES)
            raise ValueError(f"Alergias no reconocidas: {invalid}. Permitidas: {allowed}")
        return value


class ProfileRead(BaseModel):
    """rpta del perfil consumido por clientes autenticados"""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    nombre: str
    email: str
    alergias: list[str]
    objetivos_nutricionales: str | None
    
    
    
    
    