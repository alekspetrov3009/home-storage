"""Роутер мест хранения: список, создание, обновление, удаление (в корзину)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from app.api.deps import require_admin, require_auth
from app.api.schemas import (
    LocationCreate,
    LocationOut,
    LocationUpdate,
    TrashEntryOut,
    location_out,
    trash_entry_out,
)
from app.context import get_service
from app.domain.errors import NotFoundError

# Чтение доступно любой авторизованной роли; мутации — только администратору.
router = APIRouter(prefix="/api", tags=["locations"], dependencies=[Depends(require_auth)])


def _box_counts(boxes: Any) -> dict[str, int]:
    """Карта «ID места → число ящиков» для счётчиков карточек."""
    counts: dict[str, int] = {}
    for _, box in boxes.iterrows():
        key = str(box["Место_ID"])
        counts[key] = counts.get(key, 0) + 1
    return counts


def _location_out_by_id(service, location_id: str) -> LocationOut:
    """Свежий LocationOut после сброса кэша; NotFoundError, если места нет."""
    counts = _box_counts(service.load_boxes())
    for _, row in service.load_locations().iterrows():
        if str(row["ID"]) == location_id:
            return location_out(row, counts.get(location_id, 0))
    raise NotFoundError(f"Место хранения с ID {location_id} не найдено.")


@router.get("/locations", response_model=list[LocationOut])
def list_locations() -> list[LocationOut]:
    """Все места хранения с числом ящиков в каждом."""
    service = get_service()
    counts = _box_counts(service.load_boxes())
    return [
        location_out(row, counts.get(str(row["ID"]), 0))
        for _, row in service.load_locations().iterrows()
    ]


@router.post("/locations", response_model=LocationOut, status_code=201, dependencies=[Depends(require_admin)])
def create_location(payload: LocationCreate) -> LocationOut:
    """Создаёт место хранения. Одноимённое (без учёта регистра) — 409."""
    service = get_service()
    location_id = service.create_location(payload.name, payload.description)
    service.clear_cache()
    return _location_out_by_id(service, location_id)


@router.patch("/locations/{location_id}", response_model=LocationOut, dependencies=[Depends(require_admin)])
def update_location(location_id: str, payload: LocationUpdate) -> LocationOut:
    """Частичное обновление места: название и описание.

    Переименование в уже занятое имя (без учёта регистра) — 409; своё
    текущее имя дубликатом не считается. Ящики остаются привязанными.
    """
    service = get_service()
    fields: dict[str, Any] = {}
    if payload.name is not None:
        fields["Название"] = payload.name
    if payload.description is not None:
        fields["Описание"] = payload.description
    if fields:
        service.update_location(location_id, fields)
        service.clear_cache()
    return _location_out_by_id(service, location_id)


@router.delete("/locations/{location_id}", response_model=TrashEntryOut, dependencies=[Depends(require_admin)])
def delete_location(location_id: str) -> TrashEntryOut:
    """Убирает место хранения в корзину; ящики остаются «без места»."""
    service = get_service()
    entry = service.delete_location(location_id)
    service.clear_cache()
    return trash_entry_out(entry)
