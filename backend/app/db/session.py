"""Motor sqlmodel y sesiones de bd de solicitud."""

from collections.abc import Generator

from sqlmodel import Session, SQLModel, create_engine

from app.core.config import settings

connect_args = (
    {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
)
engine = create_engine(settings.database_url, echo=False, connect_args=connect_args)


def init_db() -> None:
    """Crea tablas para dev local cuando las migraciones aun no se aplican"""
    from app.models.user import User  # noqa: F401

    SQLModel.metadata.create_all(engine)


def get_session() -> Generator[Session, None, None]:
    """devuelve una sesion de bd por solicitud"""
    with Session(engine) as session:
        yield session
