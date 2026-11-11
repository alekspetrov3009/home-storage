"""Роутер health и сводной статистики.

Никакой бизнес-логики — только вызовы сервиса и сборка ответа. Ошибки
хранилища не ловятся: их статус и текст назначают exception-хендлеры
в ``app.api.main`` (``StorageError`` → 503 с текстом-контрактом).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import require_auth
from app.api.schemas import HealthResponse, StatsResponse
from app.config import get_config
from app.context import get_service
from app.helpers import qty_total

router = APIRouter(prefix="/api", tags=["service"])


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """Проверка живости API (публичная — без данных склада).

    ``registration_open`` — подсказка фронтенду: показывать ли переключатель
    «Регистрация» на странице входа (REGISTRATION_MODE)."""
    return HealthResponse(status="ok", registration_open=get_config().registration_open)


@router.get("/stats", response_model=StatsResponse, dependencies=[Depends(require_auth)])
def stats() -> StatsResponse:
    """Сводная статистика: ящики, вещи, единицы и места хранения."""
    service = get_service()
    boxes = service.load_boxes()
    items = service.load_items()
    locations = service.load_locations()
    return StatsResponse(
        boxes=int(len(boxes)),
        items=int(len(items)),
        units=qty_total(items),
        locations=int(len(locations)),
    )
