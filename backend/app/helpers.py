"""Чистые хелперы данных: подписи селектов, очистка ячеек, суммы, сравнение.

Функции не зависят от обвязки интерфейса и работают напрямую с DataFrame,
поэтому покрываются тестами без запуска приложения.
"""

from __future__ import annotations

from collections import Counter
from typing import Any, Mapping

import pandas as pd

from app.domain.categories import normalize_category

# Подписи отсутствующих родителей.
NO_BOX_LABEL = "— без ящика —"
NO_LOCATION_LABEL = "— без места хранения —"


def location_label_map(locations: pd.DataFrame) -> dict[str, str]:
    """ID места хранения -> название для выпадающих списков."""
    return {str(row["ID"]): str(row["Название"]) for _, row in locations.iterrows()}


def box_label_map(boxes: pd.DataFrame, locations: pd.DataFrame) -> dict[str, str]:
    """ID ящика -> читаемая подпись «Ящик · Место» для выпадающих списков.

    Имена ящиков не уникальны (в отличие от мест хранения), а все селекты
    строят обратную карту «подпись -> ID». При повторе названия подписи
    различаются суффиксом « · #xxxx» (последние 4 символа ID), иначе вещь
    молча уехала бы в другой ящик с тем же именем. Формат файла не меняется.
    """
    loc_names = location_label_map(locations)
    base: dict[str, str] = {}
    for _, row in boxes.iterrows():
        place = loc_names.get(str(row["Место_ID"]), "")
        name = str(row["Название"])
        base[str(row["ID"])] = f"{name} · {place}" if place else name

    counts = Counter(base.values())
    labels: dict[str, str] = {}
    used: set[str] = set()
    for box_id, label in base.items():
        if counts[label] > 1 or label == NO_BOX_LABEL:
            label = f"{label} · #{box_id[-4:]}"
        while label in used:  # крайний случай: суффикс тоже совпал
            label += "#"
        used.add(label)
        labels[box_id] = label
    return labels


def clean_text(value: Any) -> str:
    """NaN/None-безопасное строковое значение ячейки таблицы.

    ``NaN or ""`` в Python — truthy, поэтому наивный ``str(cell or "")``
    даёт «nan» для пустых ячеек строк, добавленных при редактировании.
    """
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):  # нескалярные значения не бывают NaN
        pass
    return str(value).strip()


def clean_id(value: Any) -> str:
    """ID из ячейки таблицы: пустая строка вместо None/NaN."""
    return clean_text(value)


def to_qty(value: Any) -> int:
    """Безопасное приведение ячейки «Количество» к целому.

    Текст и NaN дают 0 вместо ValueError/TypeError; отрицательное значение
    клампится в 0 — данные приходят из редактируемых пользователем таблиц.
    """
    num = pd.to_numeric(value, errors="coerce")
    if pd.isna(num):
        return 0
    return max(0, int(num))


def qty_total(items: pd.DataFrame) -> int:
    """Сумма «Количество» по вещам, устойчивая к тексту в вручную правленом файле.

    ``df["Количество"].sum()`` на object-колонке падает с TypeError, поэтому
    перед суммированием значения приводятся к числам.
    """
    if items.empty or "Количество" not in items.columns:
        return 0
    numbers = pd.to_numeric(items["Количество"], errors="coerce").fillna(0)
    return int(numbers.sum())


def item_row_changed(
    original: pd.Series, values: Mapping[str, Any], known_categories: list[str] | None = None
) -> bool:
    """True, если отредактированная строка фактически отличается от исходной.

    ``values`` — значения, которые редактор собирается записать; обе стороны
    сравниваются в нормализованном виде (пробелы срезаны, количество целым,
    категория — каноническое написание), чтобы неизменённые строки не
    получали новую отметку «Обновлён» при каждом сохранении.
    """
    options = known_categories or []
    same = (
        clean_text(original.get("Название", "")) == clean_text(values.get("Название", ""))
        and clean_text(original.get("Ящик_ID", "")) == clean_text(values.get("Ящик_ID", ""))
        and to_qty(original.get("Количество", 0)) == to_qty(values.get("Количество", 0))
        and normalize_category(clean_text(original.get("Категория", "")), options)
        == normalize_category(clean_text(values.get("Категория", "")), options)
        and clean_text(original.get("Заметки", "")) == clean_text(values.get("Заметки", ""))
    )
    return not same
