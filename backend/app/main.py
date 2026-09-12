"""MealMuse FastAPI application."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.db.session import init_db
from app.routers.auth import router as auth_router


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Initialize development tables before serving requests."""
    init_db()
    yield


app = FastAPI(title="MealMuse API", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(auth_router)


@app.get("/health", tags=["health"])
def health() -> dict[str, str]:
    """Return a lightweight service health response."""
    return {"status": "ok"}
