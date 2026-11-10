"""Роутер корзины, резервной копии и сброса кэша."""

from __future__ import annotations

from fastapi import APIRouter, Response

from app.api.schemas import (
    BackupResponse,
    ClearedResponse,
    RestoredResponse,
    SLUG_KIND,
    TrashEntryOut,
    TrashResponse,
    trash_entry_out,
)
from app.context import get_service
from app.domain.errors import ValidationError

router = APIRouter(prefix="/api", tags=["trash"])


@router.get("/trash", response_model=TrashResponse)
def list_trash() -> TrashResponse:
    """Корзина (новее сверху); просроченные записи вычищаются перед чтением."""
    service = get_service()
    purged = service.purge_expired_trash()
    service.clear_cache()
    return TrashResponse(
        entries=[trash_entry_out(entry) for entry in service.trash_entries()],
        purged=purged,
    )


@router.post("/trash/{kind}/{entity_id}/restore", response_model=RestoredResponse)
def restore(kind: str, entity_id: str) -> RestoredResponse:
    """Возвращает запись из корзины на исходный лист. kind ∈ item/box/location."""
    russian_kind = SLUG_KIND.get(kind)
    if russian_kind is None:
        raise ValidationError(f"Неизвестный тип записи корзины: {kind}.")
    service = get_service()
    name = service.restore(russian_kind, entity_id)
    service.clear_cache()
    return RestoredResponse(name=name)


@router.delete("/trash", response_model=ClearedResponse)
def clear_trash() -> ClearedResponse:
    """Полностью опустошает корзину."""
    service = get_service()
    deleted = service.clear_trash()
    service.clear_cache()
    return ClearedResponse(deleted=deleted)


@router.post("/backup", response_model=BackupResponse)
def backup() -> BackupResponse:
    """Создаёт копию файла данных рядом с оригиналом."""
    return BackupResponse(path=get_service().backup_file())


@router.post("/cache/clear", status_code=204, response_class=Response)
def clear_cache() -> Response:
    """Сбрасывает кэш чтений (30 секунд) после внешних изменений файла."""
    get_service().clear_cache()
    return Response(status_code=204)
