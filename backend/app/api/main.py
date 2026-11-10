"""Фабрика FastAPI-приложения и точка входа uvicorn.

Запуск: ``uvicorn app.api.main:app --port 8000`` (из каталога ``backend/``).
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.config import get_config


def create_app() -> FastAPI:
    """Собирает приложение: CORS для фронтенда + роутеры API."""
    app = FastAPI(title="Домашний склад API")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(get_config().cors_origins),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router)
    return app


app = create_app()
