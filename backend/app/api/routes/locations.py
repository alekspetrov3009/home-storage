"""Роутер мест хранения: список, создание, удаление (в корзину)."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.schemas import (
    LocationCreate,
    LocationOut,
    TrashEntryOut,
    location_out,
    trash_entry_out,
)
from app.context import get_service
from app.domain.errors import NotFoundError

router = APIRouter(prefix="/api", tags=["locations"])


@router.get("/locations", response_model=list[LocationOut])
def list_locations() -> list[LocationOut]:
    """Все места хранения с числом ящиков в каждом."""
    service = get_service()
    locations = service.load_locations()
    box_counts: dict[str, int] = {}
    for _, box in service.load_boxes().iterrows():
        key = str(box["Место_ID"])
        box_counts[key] = box_counts.get(key, 0) + 1
    return [
        location_out(row, box_counts.get(str(row["ID"]), 0))
        for _, row in locations.iterrows()
    ]


@router.post("/locations", response_model=LocationOut, status_code=201)
def create_location(payload: LocationCreate) -> LocationOut:
    """Создаёт место хранения. Одноимённое (без учёта регистра) — 409."""
    service = get_service()
    location_id = service.create_location(payload.name, payload.description)
    service.clear_cache()
    for _, row in service.load_locations().iterrows():
        if str(row["ID"]) == location_id:
            return location_out(row, 0)
    raise NotFoundError(f"Место хранения с ID {location_id} не найдено.")


@router.delete("/locations/{location_id}", response_model=TrashEntryOut)
def delete_location(location_id: str) -> TrashEntryOut:
    """Убирает место хранения в корзину; ящики остаются «без места»."""
    service = get_service()
    entry = service.delete_location(location_id)
    service.clear_cache()
    return trash_entry_out(entry)
