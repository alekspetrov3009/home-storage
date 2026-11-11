"""Корзина: типы удалённых сущностей, запись и срок хранения.

Чистая логика без openpyxl и обвязки интерфейса: расчёт истечения срока
(30 дней) и кодирование исходной строки в JSON выделены сюда, чтобы их
можно было тестировать отдельно от хранилища.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Mapping

# Тип записи в корзине (значения хранятся в листе «Корзина», колонка «Тип»).
TRASH_KIND_ITEM = "вещь"
TRASH_KIND_BOX = "ящик"
TRASH_KIND_LOCATION = "место"

# Сколько дней запись хранится в корзине, после чего скрывается и вычищается.
TRASH_RETENTION_DAYS = 30

_TS_FORMAT = "%Y-%m-%d %H:%M:%S"


@dataclass(frozen=True)
class DeletedEntry:
    """Одна запись корзины: что удалили, откуда и когда."""

    kind: str
    id: str
    name: str
    parent_id: str
    deleted_at: str
    data: dict[str, Any]

    @classmethod
    def from_row(cls, row: Mapping[str, Any]) -> "DeletedEntry":
        """Собирает запись из строки листа «Корзина» (колонки TRASH_FIELDS)."""
        return cls(
            kind=str(row.get("Тип", "")),
            id=str(row.get("ID", "")),
            name=str(row.get("Название", "")),
            parent_id=str(row.get("Родитель_ID", "") or ""),
            deleted_at=str(row.get("Дата удаления", "") or ""),
            data=decode_data(row.get("Данные", "")),
        )


def parse_ts(value: Any) -> datetime | None:
    """Разбирает отметку времени формата файла данных; None, если не получилось."""
    try:
        return datetime.strptime(str(value).strip(), _TS_FORMAT)
    except (ValueError, TypeError):
        return None


def is_expired(
    deleted_at: Any, now: datetime, days: int = TRASH_RETENTION_DAYS
) -> bool:
    """True, если запись удалена раньше, чем ``days`` дней назад.

    Неразбираемая отметка считается НЕ истекшей: такую запись виднее
    оставить в корзине (и её можно восстановить вручную), чем молча вычистить.
    """
    parsed = parse_ts(deleted_at)
    if parsed is None:
        return False
    return parsed < now - timedelta(days=days)


def encode_data(record: Mapping[str, Any]) -> str:
    """Исходная строка листа -> JSON для колонки «Данные»."""
    return json.dumps(
        {str(k): "" if v is None else v for k, v in record.items()},
        ensure_ascii=False,
    )


def decode_data(raw: Any) -> dict[str, Any]:
    """Колонка «Данные» -> словарь исходных значений; устойчиво к мусору."""
    try:
        parsed = json.loads(str(raw or "{}"))
    except (ValueError, TypeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}
