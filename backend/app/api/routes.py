"""Роутеры API: health и сводная статистика.

Никакой бизнес-логики — только вызовы сервиса и сборка ответа. Ошибка
хранилища отдаётся как 503 с текстом-контрактом из ``StorageError``.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.context import get_service
from app.domain.errors import StorageError
from app.helpers import qty_total
from app.api.schemas import HealthResponse, StatsResponse

router = APIRouter(prefix="/api")


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """Проверка живости API."""
    return HealthResponse(status="ok")


@router.get("/stats", response_model=StatsResponse)
def stats() -> StatsResponse:
    """Сводная статистика: ящики, вещи, единицы и места хранения."""
    service = get_service()
    try:
        boxes = service.load_boxes()
        items = service.load_items()
        locations = service.load_locations()
    except StorageError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return StatsResponse(
        boxes=int(len(boxes)),
        items=int(len(items)),
        units=qty_total(items),
        locations=int(len(locations)),
    )
