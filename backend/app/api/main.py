"""Фабрика FastAPI-приложения и точка входа uvicorn.

Запуск: ``uvicorn app.api.main:app --port 8000`` (из каталога ``backend/``).
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import api_router
from app.config import get_config
from app.domain.errors import ConflictError, NotFoundError, StorageError, ValidationError


def _detail(status_code: int):
    """Хендлер, отдающий ошибку как ``{"detail": str(exc)}`` с нужным статусом.

    Тексты исключений — пользовательский контракт, отдаются как есть.
    """

    def handler(request: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(status_code=status_code, content={"detail": str(exc)})

    return handler


def create_app() -> FastAPI:
    """Собирает приложение: CORS для фронтенда, роутеры и обработчики ошибок.

    Starlette ищет хендлер по MRO: ValidationError/NotFoundError/ConflictError —
    подклассы StorageError, поэтому каждый тип получает свой статус (400/404/409),
    а прочие сбои хранилища — 503. Порядок объявления не важен.
    """
    app = FastAPI(title="Домашний склад API")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(get_config().cors_origins),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.exception_handler(ValidationError)(_detail(400))
    app.exception_handler(NotFoundError)(_detail(404))
    app.exception_handler(ConflictError)(_detail(409))
    app.exception_handler(StorageError)(_detail(503))
    app.include_router(api_router)
    return app


app = create_app()
