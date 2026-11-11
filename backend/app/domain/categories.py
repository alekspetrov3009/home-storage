"""Общий справочник категорий.

Категории не хранятся отдельно — список складывается из значений колонки
«Категория» листа «Вещи». Дедуп пишется без учёта регистра («инструменты»
и «Инструменты» — одна категория), каноническим считается первое
встретившееся написание. Чистая функция живёт в домене, чтобы сервисный
слой и клиенты API пользовались одним и тем же алгоритмом.
"""

from __future__ import annotations

from typing import Any, Iterable

import pandas as pd

from app.domain.errors import ValidationError

NEW_CATEGORY = "__new_category__"  # служебный вариант «создать новую»


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


def category_options(items: pd.DataFrame) -> list[str]:
    """Общий список категорий: уникальные значения из всех вещей, по алфавиту.

    Делегирует общему алгоритму — тому же, что использует
    ``InventoryService.get_categories``, чтобы список в формах и в сервисе
    совпадал. Дубли пишутся без учёта регистра («инструменты» и
    «Инструменты» — одна категория); каноническим считается первое
    встретившееся написание.
    """
    if items.empty or "Категория" not in items.columns:
        return []
    return unique_categories(items["Категория"].tolist())


def combined_categories(stored: Iterable[Any], used: Iterable[Any]) -> list[str]:
    """Справочник категорий: сохранённые отдельно + используемые у вещей.

    Категории могут существовать и без вещей (добавлены заранее через
    настройки), поэтому справочник — объединение двух источников. Дедуп
    и сортировка те же, что у списка из вещей: без учёта регистра, по
    алфавиту, каноническим считается первое встретившееся написание.
    """
    return unique_categories([*stored, *used])


def find_category(name: str, options: Iterable[Any]) -> str | None:
    """Каноническое написание категории без учёта регистра, либо None."""
    lowered = str(name or "").strip().lower()
    if not lowered:
        return None
    for option in options:
        canonical = str(option).strip()
        if canonical.lower() == lowered:
            return canonical
    return None


def validate_category_name(value: str) -> str:
    """Проверяет имя категории справочника: непустое после обрезки пробелов."""
    name = str(value or "").strip()
    if not name:
        raise ValidationError("Укажите название категории.")
    return name


def normalize_category(value: str, options: list[str]) -> str:
    """Свободный ввод категории: обрезает пробелы, пустое — «без категории».

    Совпадение с уже существующей категорией без учёта регистра сводится к её
    каноническому написанию, чтобы не плодить дубли вида «инструменты» и
    «Инструменты». Новое имя сохраняется как введено (с обрезкой).
    """
    name = str(value or "").strip()
    if not name:
        return ""
    canonical = {str(option).strip().lower(): str(option).strip() for option in options}
    return canonical.get(name.lower(), name)


def resolve_category(choice: str, new_name: str, options: list[str]) -> str:
    """Итоговое имя категории из выбранного варианта (чистая функция).

    ``choice`` — выбранное значение (в том числе сентинел ``NEW_CATEGORY``),
    ``new_name`` — название новой категории. Пустое имя новой категории —
    ошибка: вещь не должна молча сохраниться «без категории».
    """
    if choice != NEW_CATEGORY:
        return normalize_category(choice, options)
    name = normalize_category(new_name, options)
    if not name:
        raise ValidationError("Укажите название новой категории.")
    return name
