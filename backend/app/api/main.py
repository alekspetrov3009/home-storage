"""Фабрика FastAPI-приложения и точка входа uvicorn.

Запуск: ``uvicorn app.api.main:app --port 8000`` (из каталога ``backend/``).
"""

from __future__ import annotations

from urllib.parse import urlsplit

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.api.routes import api_router
from app.config import get_config
from app.domain.errors import (
    AuthError,
    ConflictError,
    ForbiddenError,
    NotFoundError,
    StorageError,
    ValidationError,
)

# Методы, меняющие состояние: для них действует проверка Origin (CSRF).
_MUTATING_METHODS = ("POST", "PATCH", "PUT", "DELETE")


def _origin_netloc(origin: str) -> str:
    """``https://sklad.example.com`` → ``sklad.example.com`` (host[:port])."""
    try:
        parts = urlsplit(origin.strip())
    except ValueError:
        return ""
    return parts.netloc.lower()


def _allowed_origins(request: Request) -> set[str]:
    """Источники, с которых разрешены мутации: BASE_URL (публичный адрес),
    CORS_ORIGINS и собственный Host запроса (за прокси nginx подставляет
    исходный адрес). Для каждого источника разрешается и вариант без порта:
    прокси и обратные прокси нормализуют порт по-разному (Origin всегда
    несёт порт нестандартного порта, Host может прийти без него). Запросы
    без Origin (curl, мобильные клиенты, server-to-server) не проверяются."""
    config = get_config()
    allowed: set[str] = set()

    def add(netloc: str) -> None:
        if not netloc:
            return
        allowed.add(netloc)
        # ``sklad.example.com:8081`` → также ``sklad.example.com``.
        allowed.add(urlsplit(f"//{netloc}").hostname or "")

    add(_origin_netloc(config.base_url))
    for origin in config.cors_origins:
        add(_origin_netloc(origin))
    host = request.headers.get("host", "")
    if host:
        add(host.lower())
    allowed.discard("")
    return allowed


class OriginCheckMiddleware(BaseHTTPMiddleware):
    """Defense-in-depth против CSRF.

    Основная защита — SameSite=Lax у cookie сессии (кросс-сайтовые POST
    не несут cookie). Дополнительно мутации с присланным Origin-заголовком
    принимаются только от разрешённых источников; запросы без Origin
    (curl, мобильные клиенты, server-to-server) проходят как раньше.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        if request.method in _MUTATING_METHODS:
            origin = request.headers.get("origin", "")
            if origin:
                netloc = _origin_netloc(origin)
                allowed = _allowed_origins(request)
                # Совпадение по netloc (host[:port]) или по имени хоста:
                # прокси и Origin нормализуют порт по-разному, а браузер
                # всегда присылает настоящий Origin страницы-источника.
                hostname = urlsplit(f"//{netloc}").hostname or ""
                if netloc not in allowed and hostname not in allowed:
                    return JSONResponse(
                        status_code=403,
                        content={"detail": "Запрос отклонён: источник не разрешён."},
                    )
        return await call_next(request)


def _detail(status_code: int):
    """Хендлер, отдающий ошибку как ``{"detail": str(exc)}`` с нужным статусом.

    Тексты исключений — пользовательский контракт, отдаются как есть.
    """

    def handler(request: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(status_code=status_code, content={"detail": str(exc)})

    return handler


def create_app() -> FastAPI:
    """Собирает приложение: CORS, проверку Origin, роутеры и хендлеры ошибок.

    Starlette ищет хендлер по MRO: ValidationError/NotFoundError/ConflictError —
    подклассы StorageError, поэтому каждый тип получает свой статус (400/404/409),
    AuthError/ForbiddenError — 401/403, а прочие сбои хранилища — 503.
    Порядок объявления не важен.

    DOCS_ENABLED=0 отключает /docs, /redoc и /openapi.json — интерактивная
    документация не отдаётся на публичный хост.
    """
    config = get_config()
    if config.docs_enabled:
        app = FastAPI(title="Домашний склад API")
    else:
        app = FastAPI(
            title="Домашний склад API",
            docs_url=None,
            redoc_url=None,
            openapi_url=None,
        )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(config.cors_origins),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(OriginCheckMiddleware)
    app.exception_handler(ValidationError)(_detail(400))
    app.exception_handler(NotFoundError)(_detail(404))
    app.exception_handler(ConflictError)(_detail(409))
    app.exception_handler(AuthError)(_detail(401))
    app.exception_handler(ForbiddenError)(_detail(403))
    app.exception_handler(StorageError)(_detail(503))
    app.include_router(api_router)
    return app


app = create_app()
