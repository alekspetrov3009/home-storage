"""Роутер категорий: справочник + корректирование из панели настроек.

Категории живут в двух местах: лист «Категории» (добавлены заранее через
настройки, могут быть без вещей) и колонка «Категория» листа «Вещи».
GET отдаёт объединение обоих источников; мутации правят справочник и вещи
за одно сохранение файла. Категория адресуется именем в теле/параметре
запроса, а не в пути: названия могут содержать «/» и любые символы.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import require_admin, require_auth

from app.api.schemas import CategoryCreate, CategoryMutationOut, CategoryUpdate
from app.context import get_service

router = APIRouter(prefix="/api", tags=["categories"], dependencies=[Depends(require_auth)])


@router.get("/categories", response_model=list[str])
def categories() -> list[str]:
    """Справочник категорий: сохранённые отдельно + используемые у вещей, по алфавиту."""
    return get_service().get_categories()


@router.post("/categories", response_model=CategoryMutationOut, status_code=201, dependencies=[Depends(require_admin)])
def create_category(payload: CategoryCreate) -> CategoryMutationOut:
    """Добавляет категорию в справочник; дубликат (без учёта регистра) — 409."""
    service = get_service()
    name = service.create_category(payload.name)
    service.clear_cache()
    return CategoryMutationOut(name=name, items_updated=0)


@router.patch("/categories", response_model=CategoryMutationOut, dependencies=[Depends(require_admin)])
def rename_category(payload: CategoryUpdate) -> CategoryMutationOut:
    """Переименовывает категорию и обновляет её у всех вещей.

    Смена только регистра легальна и сводит написание вещей к новому
    каноническому виду.
    """
    service = get_service()
    name, updated = service.rename_category(payload.name, payload.new_name)
    service.clear_cache()
    return CategoryMutationOut(name=name, items_updated=updated)


@router.delete("/categories", response_model=CategoryMutationOut, dependencies=[Depends(require_admin)])
def delete_category(name: str = "") -> CategoryMutationOut:
    """Удаляет категорию из справочника; вещи становятся «без категории»."""
    service = get_service()
    name, updated = service.delete_category(name)
    service.clear_cache()
    return CategoryMutationOut(name=name, items_updated=updated)
