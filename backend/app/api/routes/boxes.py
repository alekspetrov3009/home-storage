"""Роутер ящиков: список, деталь, создание, удаление и QR-код."""

from __future__ import annotations

import io
from typing import Any

import qrcode
from fastapi import APIRouter, Request, Response

from app.api.schemas import (
    BoxCreate,
    BoxDetail,
    BoxOut,
    BoxUpdate,
    TrashEntryOut,
    box_out,
    item_out,
    trash_entry_out,
)
from app.config import get_config
from app.context import get_service
from app.domain.errors import NotFoundError
from app.helpers import box_label_map, location_label_map, to_qty

router = APIRouter(prefix="/api", tags=["boxes"])


def _row_by_id(df: Any, record_id: str) -> Any:
    """Строка DataFrame с указанным ID или None."""
    for _, row in df.iterrows():
        if str(row["ID"]) == str(record_id):
            return row
    return None


def _items_grouped(service) -> dict[str, list[Any]]:
    """Вещи, сгруппированные по Ящик_ID (счётчики и содержимое ящиков)."""
    grouped: dict[str, list[Any]] = {}
    for _, row in service.load_items().iterrows():
        grouped.setdefault(str(row["Ящик_ID"]), []).append(row)
    return grouped


def _box_detail(service, box_id: str) -> BoxDetail:
    """BoxDetail по ID ящика; NotFoundError, если ящика нет."""
    boxes = service.load_boxes()
    row = _row_by_id(boxes, box_id)
    if row is None:
        raise NotFoundError(f"Ящик с ID {box_id} не найден.")
    locations = service.load_locations()
    location_names = location_label_map(locations)
    labels = box_label_map(boxes, locations)
    members = [
        item_out(member, labels.get(box_id))
        for member in _items_grouped(service).get(box_id, [])
    ]
    units = sum(member.quantity for member in members)
    base = box_out(
        row,
        location_names.get(str(row["Место_ID"])),
        item_count=len(members),
        unit_count=units,
    )
    return BoxDetail(**base.model_dump(), items=members)


@router.get("/boxes", response_model=list[BoxOut])
def list_boxes() -> list[BoxOut]:
    """Все ящики с местом хранения и счётчиками вещей."""
    service = get_service()
    boxes = service.load_boxes()
    location_names = location_label_map(service.load_locations())
    grouped = _items_grouped(service)
    return [
        box_out(
            row,
            location_names.get(str(row["Место_ID"])),
            item_count=len(grouped.get(str(row["ID"]), [])),
            unit_count=sum(
                to_qty(member["Количество"]) for member in grouped.get(str(row["ID"]), [])
            ),
        )
        for _, row in boxes.iterrows()
    ]


@router.post("/boxes", response_model=BoxOut, status_code=201)
def create_box(payload: BoxCreate) -> BoxOut:
    """Создаёт ящик; несуществующее место хранения — 404."""
    service = get_service()
    box_id = service.create_box(payload.name, payload.location_id, payload.description)
    service.clear_cache()
    return _box_detail(service, box_id)


@router.get("/boxes/{box_id}", response_model=BoxDetail)
def get_box(box_id: str) -> BoxDetail:
    """Ящик со счётчиками и вещами внутри."""
    return _box_detail(get_service(), box_id)


@router.patch("/boxes/{box_id}", response_model=BoxDetail)
def update_box(box_id: str, payload: BoxUpdate) -> BoxDetail:
    """Частичное обновление ящика: название, место, описание.

    ``location_id`` обрабатывается как перенос: пустая строка или null —
    «без места хранения», несуществующее место — 404 (текст add_box).
    Содержимое не трогается; ответ — свежая деталь со счётчиками.
    """
    service = get_service()
    provided = payload.model_fields_set

    fields: dict[str, Any] = {}
    if payload.name is not None:
        fields["Название"] = payload.name
    if "location_id" in provided:
        fields["Место_ID"] = (payload.location_id or "").strip()
    if payload.description is not None:
        fields["Описание"] = payload.description

    if fields:
        service.update_box(box_id, fields)
        service.clear_cache()
    return _box_detail(service, box_id)


@router.delete("/boxes/{box_id}", response_model=TrashEntryOut)
def delete_box(box_id: str) -> TrashEntryOut:
    """Убирает ящик в корзину; вещи остаются с прежним Ящик_ID."""
    service = get_service()
    entry = service.delete_box(box_id)
    service.clear_cache()
    return trash_entry_out(entry)


@router.get("/boxes/{box_id}/qr")
def box_qr(box_id: str, request: Request) -> Response:
    """PNG QR-код со ссылкой на страницу ящика (формат прежних QR).

    Ссылка строится от BASE_URL, а без него — от адреса запроса.
    """
    service = get_service()
    boxes = service.load_boxes()
    if _row_by_id(boxes, box_id) is None:
        raise NotFoundError(f"Ящик с ID {box_id} не найден.")
    base = get_config().base_url or str(request.base_url).rstrip("/")
    link = f"{base}/box?box={box_id}"
    buffer = io.BytesIO()
    qrcode.make(link).save(buffer, format="PNG")
    return Response(content=buffer.getvalue(), media_type="image/png")
