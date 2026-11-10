"""Доменные сущности и их инварианты.

Обычные dataclass-модели без внешних зависимостей. Инварианты проверяются
в ``__post_init__``: непустое название, количество — целое неотрицательное
число. Сценарии сервисного слоя создают объекты моделей для валидации входа
перед записью в хранилище.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from app.domain.errors import ValidationError


def _require_name(name: Any, what: str) -> str:
    name = str(name or "").strip()
    if not name:
        raise ValidationError(f"Укажите название {what}.")
    return name


def _require_quantity(quantity: Any) -> int:
    # bool — это int в Python, но количеством он быть не может.
    if isinstance(quantity, bool) or not isinstance(quantity, int):
        raise ValidationError("Количество должно быть целым числом.")
    if quantity < 0:
        raise ValidationError("Количество не может быть отрицательным.")
    return quantity


@dataclass(frozen=True)
class Location:
    """Место хранения: комната, полка, шкаф."""

    id: str
    name: str
    description: str = ""
    created: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "name", _require_name(self.name, "места хранения"))

    @classmethod
    def from_row(cls, row: Mapping[str, Any]) -> "Location":
        return cls(
            id=str(row.get("ID", "")),
            name=str(row.get("Название", "")),
            description=str(row.get("Описание", "")),
            created=str(row.get("Создан", "")),
        )


@dataclass(frozen=True)
class Box:
    """Ящик, привязанный к месту хранения по ID (пустая строка — без места)."""

    id: str
    name: str
    location_id: str = ""
    description: str = ""
    created: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "name", _require_name(self.name, "ящика"))

    @classmethod
    def from_row(cls, row: Mapping[str, Any]) -> "Box":
        return cls(
            id=str(row.get("ID", "")),
            name=str(row.get("Название", "")),
            location_id=str(row.get("Место_ID", "")),
            description=str(row.get("Описание", "")),
            created=str(row.get("Создан", "")),
        )


@dataclass(frozen=True)
class Item:
    """Вещь внутри ящика.

    Нулевое количество допустимо: интерфейс разрешает «убавить до нуля»,
    поэтому инвариант — неотрицательное целое, а не строго положительное.
    """

    id: str
    name: str
    box_id: str
    quantity: int
    category: str = ""
    notes: str = ""
    updated: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "name", _require_name(self.name, "вещи"))
        object.__setattr__(self, "quantity", _require_quantity(self.quantity))

    @classmethod
    def from_row(cls, row: Mapping[str, Any]) -> "Item":
        return cls(
            id=str(row.get("ID", "")),
            name=str(row.get("Название", "")),
            box_id=str(row.get("Ящик_ID", "")),
            quantity=int(row.get("Количество", 0) or 0),
            category=str(row.get("Категория", "")),
            notes=str(row.get("Заметки", "")),
            updated=str(row.get("Обновлён", "")),
        )
