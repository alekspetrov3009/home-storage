"""Роутер вещей: CRUD, массовые операции и поиск."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from app.api.deps import require_admin, require_auth
from app.api.schemas import (
    ItemCreate,
    ItemOut,
    ItemUpdate,
    ItemsReplace,
    MoveIn,
    SavedResponse,
    TrashEntryOut,
    item_out,
    trash_entry_out,
)
from app.context import get_service
from app.domain.categories import normalize_category
from app.domain.errors import NotFoundError
from app.helpers import box_label_map
from app.services.inventory_service import InventoryService

# Чтение доступно любой авторизованной роли; мутации — только администратору.
router = APIRouter(prefix="/api", tags=["items"], dependencies=[Depends(require_auth)])


def _row_by_id(df: Any, record_id: str) -> Any:
    """Строка DataFrame с указанным ID или None."""
    for _, row in df.iterrows():
        if str(row["ID"]) == str(record_id):
            return row
    return None


def _read_item(service, item_id: str) -> ItemOut:
    """Вещь из файла после сброса кэша; NotFoundError, если её нет."""
    items = service.load_items()
    row = _row_by_id(items, item_id)
    if row is None:
        raise NotFoundError(f"Вещь с ID {item_id} не найдена (возможно, удалена).")
    labels = box_label_map(service.load_boxes(), service.load_locations())
    return item_out(row, labels.get(str(row["Ящик_ID"])))


@router.get("/items", response_model=list[ItemOut])
def list_items(box_id: str = "", category: str = "") -> list[ItemOut]:
    """Все вещи; фильтры по ящику (точное ID) и категории (без учёта регистра)."""
    service = get_service()
    labels = box_label_map(service.load_boxes(), service.load_locations())
    wanted_category = category.strip().lower()
    result: list[ItemOut] = []
    for _, row in service.load_items().iterrows():
        if box_id and str(row["Ящик_ID"]) != box_id:
            continue
        if wanted_category and str(row["Категория"]).strip().lower() != wanted_category:
            continue
        result.append(item_out(row, labels.get(str(row["Ящик_ID"]))))
    return result


@router.post("/items", response_model=ItemOut, status_code=201, dependencies=[Depends(require_admin)])
def create_item(payload: ItemCreate) -> ItemOut:
    """Добавляет вещь; категория нормализуется к каноническому написанию."""
    service = get_service()
    category = normalize_category(payload.category, service.get_categories())
    item_id = service.create_item(
        payload.name, payload.box_id, payload.quantity, category, payload.notes
    )
    service.clear_cache()
    return _read_item(service, item_id)


@router.patch("/items/{item_id}", response_model=ItemOut, dependencies=[Depends(require_admin)])
def update_item(item_id: str, payload: ItemUpdate) -> ItemOut:
    """Частичное обновление вещи.

    ``box_id`` обрабатывается как перенос (с проверкой существования ящика);
    пустая строка или null — «без ящика», как выбор «— без ящика —» в формах.
    Остальные поля уходят в точечное обновление, «Обновлён» ставит сервис.
    """
    service = get_service()
    provided = payload.model_fields_set

    if "box_id" in provided:
        target = (payload.box_id or "").strip()
        if target:
            service.move_item(item_id, target)
        else:
            service.update_item(item_id, {"Ящик_ID": ""})

    fields: dict[str, Any] = {}
    if payload.name is not None:
        fields["Название"] = payload.name
    if payload.quantity is not None:
        fields["Количество"] = payload.quantity
    if payload.notes is not None:
        fields["Заметки"] = payload.notes
    if payload.category is not None:
        fields["Категория"] = normalize_category(
            payload.category, service.get_categories()
        )
    if fields:
        service.update_item(item_id, fields)

    service.clear_cache()
    return _read_item(service, item_id)


@router.post("/items/{item_id}/move", response_model=ItemOut, dependencies=[Depends(require_admin)])
def move_item(item_id: str, payload: MoveIn) -> ItemOut:
    """Переносит вещь в другой ящик; несуществующий ящик — 404."""
    service = get_service()
    service.move_item(item_id, payload.box_id)
    service.clear_cache()
    return _read_item(service, item_id)


@router.delete("/items/{item_id}", response_model=TrashEntryOut, dependencies=[Depends(require_admin)])
def delete_item(item_id: str) -> TrashEntryOut:
    """Убирает вещь в корзину целиком (исходная строка сохраняется)."""
    service = get_service()
    entry = service.delete_item(item_id)
    service.clear_cache()
    return trash_entry_out(entry)


@router.delete("/items", response_model=list[TrashEntryOut], dependencies=[Depends(require_admin)])
def delete_items(ids: str) -> list[TrashEntryOut]:
    """Массово убирает вещи в корзину за одно сохранение файла.

    ``ids`` — ID через запятую; дубликаты и отсутствующие ID пропускаются.
    """
    service = get_service()
    item_ids = [part.strip() for part in ids.split(",") if part.strip()]
    entries = service.delete_items(item_ids)
    service.clear_cache()
    return [trash_entry_out(entry) for entry in entries]


@router.put("/items", response_model=SavedResponse, dependencies=[Depends(require_admin)])
def replace_items(payload: ItemsReplace) -> SavedResponse:
    """Bulk-save таблицы вещей: полный перезапись листа редактором.

    Возвращает число записанных строк; нормализация и отметка «Обновлён» —
    в ``InventoryService.save_items_table``.
    """
    service = get_service()
    saved = service.save_items_table([row.model_dump() for row in payload.items])
    service.clear_cache()
    return SavedResponse(saved=saved)


@router.get("/search", response_model=list[ItemOut])
def search(q: str = "") -> list[ItemOut]:
    """Поиск по названию, категории, заметкам и подписи ящика."""
    service = get_service()
    items = service.load_items()
    labels = box_label_map(service.load_boxes(), service.load_locations())
    found = set(InventoryService.search_item_ids(items, labels, q))
    return [
        item_out(row, labels.get(str(row["Ящик_ID"])))
        for _, row in items.iterrows()
        if str(row["ID"]) in found
    ]
