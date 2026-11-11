"""Общий справочник категорий.

Справочник хранится на листе «Категории» (создаётся лениво, через настройки)
и пополняется категориями, уже используемыми у вещей; дедуп пишется без учёта
регистра («инструменты» и «Инструменты» — одна категория), каноническим
считается первое встретившееся написание. Чистые функции живут в домене,
чтобы сервисный слой пользовался одним и тем же алгоритмом (пикер формы —
на фронтенде, его зеркала в API нет).
"""

from __future__ import annotations

from typing import Any, Iterable

from app.domain.errors import ValidationError


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
