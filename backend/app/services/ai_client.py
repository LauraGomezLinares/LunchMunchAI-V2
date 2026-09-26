"""Provider-neutral asynchronous interface for recipe language models."""

import json
import os
from abc import ABC, abstractmethod
from typing import Any

import httpx

from app.schemas.recipes import RecipeRead


class AIProvider(ABC):
    """Common interface implemented by recipe generation providers."""

    @abstractmethod
    async def generate_recipe(self, prompt: str) -> RecipeRead:
        """Generate one recipe from the assembled system prompt."""


class MockProvider(AIProvider):
    """Deterministic local provider for development and tests."""

    async def generate_recipe(self, prompt: str) -> RecipeRead:
        del prompt
        return RecipeRead(
            nombre="Bowl de arroz y verduras",
            tiempo_estimado_minutos=20,
            porciones=2,
            calorias=420,
            ingredientes=["arroz", "tomate", "espinaca", "aceite de oliva"],
            pasos=["Cocina el arroz.", "Saltea las verduras y sirve sobre el arroz."],
            apto_para_alergias=True,
        )


class APIProvider(AIProvider):
    """Provider for an OpenAI-compatible API configured entirely by environment."""

    async def generate_recipe(self, prompt: str) -> RecipeRead:
        api_key = os.getenv("AI_API_KEY", "")
        api_url = os.getenv("AI_API_URL", "")
        if not api_key or not api_url:
            raise RuntimeError("AI_API_KEY y AI_API_URL deben estar configuradas.")

        async with httpx.AsyncClient(timeout=None) as client:
            response = await client.post(
                api_url,
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "model": os.getenv("AI_MODEL", ""),
                    "messages": [
                        {
                            "role": "system",
                            "content": (
                                f"{prompt}\nResponde únicamente con un JSON válido "
                                "que cumpla el contrato de receta solicitado."
                            ),
                        }
                    ],
                    "response_format": {"type": "json_object"},
                },
            )
            response.raise_for_status()

        payload: dict[str, Any] = response.json()
        content = payload["choices"][0]["message"]["content"]
        return RecipeRead.model_validate(json.loads(content))


def get_ai_provider() -> AIProvider:
    """Resolve the configured implementation from AI_PROVIDER."""
    provider = os.getenv("AI_PROVIDER", "mock").strip().lower()
    if provider == "mock":
        return MockProvider()
    if provider == "api":
        return APIProvider()
    raise ValueError(f"AI_PROVIDER no reconocido: {provider}")