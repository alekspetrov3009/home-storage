"""Общий справочник категорий.

Категории не хранятся отдельно — список складывается из значений колонки
«Категория» листа «Вещи». Дедуп пишется без учёта регистра («инструменты»
и «Инструменты» — одна категория), каноническим считается первое
встретившееся написание. Чистая функция живёт в домене, чтобы сервисный
слой и UI-формы пользовались одним и тем же алгоритмом.
"""

from __future__ import annotations

from typing import Any, Iterable


def unique_categories(values: Iterable[Any]) -> list[str]:
    """Канонический список категорий: по алфавиту, без регистровых дублей."""
    unique: dict[str, str] = {}
    for value in values:
        if value is None:
            continue
        name = str(value).strip()
        if not name or name.lower() == "nan":
            continue
        unique.setdefault(name.lower(), name)
    return sorted(unique.values())
