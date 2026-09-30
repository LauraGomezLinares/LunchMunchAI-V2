"""Authenticated user profile endpoints."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.core.security import get_current_user
from app.db.session import get_session
from app.models.user import User
from app.schemas.profile import ProfileRead, ProfileUpdate

router = APIRouter(prefix="/api/v1/users", tags=["users"])


def _profile_response(user: User) -> ProfileRead:
    """Serialize only the profile fields exposed by this router."""
    allergies = user.alergias if isinstance(user.alergias, list) else []
    return ProfileRead(
        id=user.id,
        nombre=user.nombre,
        email=user.email,
        alergias=allergies,
        objetivos_nutricionales=user.objetivos_nutricionales,
    )


@router.get("/profile", response_model=ProfileRead)
def get_profile(current_user: User = Depends(get_current_user)) -> ProfileRead:
    """Return the authenticated user's profile and persisted restrictions."""
    return _profile_response(current_user)


@router.put("/profile", response_model=ProfileRead)
def update_profile(
    payload: ProfileUpdate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ProfileRead:
    """Persist allergies while leaving name and nutrition objectives untouched."""
    current_user.alergias = payload.alergias
    current_user.updated_at = datetime.now(timezone.utc)
    session.add(current_user)
    session.commit()
    session.refresh(current_user)
    return _profile_response(current_user)