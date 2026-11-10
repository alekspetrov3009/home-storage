"""Вспомогательные функции UI: чтение данных, подписи, разметка карточек.

Чистые хелперы (``clean_text``/``to_qty``/``qty_total``/``item_row_changed``)
не обращаются к Streamlit-рантайму, поэтому покрываются тестами напрямую.
"""

from __future__ import annotations

import hashlib
import html as html_lib
from collections import Counter
from typing import Any, Mapping

import pandas as pd
import streamlit as st

from app.context import get_service
from app.domain.errors import StorageError


def load_all() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Читает все три листа, показывая понятную ошибку при сбое хранилища."""
    service = get_service()
    try:
        return service.load_boxes(), service.load_items(), service.load_locations()
    except StorageError as exc:
        st.error(f"🔧 Ошибка хранилища: {exc}")
        st.stop()
    except Exception as exc:  # noqa: BLE001
        st.error(f"Не удалось прочитать файл данных: {exc}")
        st.stop()
    raise AssertionError  # недостижимо (st.stop прерывает выполнение)


def clear_caches() -> None:
    """Сбрасывает кэш данных после изменений, чтобы UI показал актуальное состояние."""
    get_service().clear_cache()


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
    from app.ui.trash import NO_BOX_LABEL

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
    """NaN/None-безопасное строковое значение ячейки редактора.

    ``NaN or ""`` в Python — truthy, поэтому наивный ``str(cell or "")``
    даёт «nan» для пустых ячеек строк, добавленных через ``num_rows="dynamic"``.
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
    """ID из ячейки редактора: пустая строка вместо None/NaN."""
    return clean_text(value)


def to_qty(value: Any) -> int:
    """Безопасное приведение ячейки «Количество» к целому.

    Текст и NaN (очищенная ячейка) дают 0 вместо ValueError/TypeError;
    отрицательное значение клампится в 0 — данные приходят из редактора.
    """
    num = pd.to_numeric(value, errors="coerce")
    if pd.isna(num):
        return 0
    return max(0, int(num))


def qty_total(items: pd.DataFrame) -> int:
    """Сумма «Количество» по вещам, устойчивая к тексту в вручную правленом файле.

    ``df["Количество"].sum()`` на object-колонке падает с TypeError и валит
    всю страницу, поэтому перед суммированием значения приводятся к числам.
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
    from app.ui.forms import normalize_category

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


def page_header(title: str, caption: str | None = None, page_key: str = "") -> None:
    """Заголовок страницы; перед ним рисует полосу отмены удаления.

    page_key — идентификатор страницы: полоса «Только что удалено» живёт
    только на той странице, где произошло удаление, и исчезает при навигации.
    """
    from app.ui.trash import render_undo_strip

    render_undo_strip(page_key)
    st.markdown(f"<h1>{html_lib.escape(title)}</h1>", unsafe_allow_html=True)
    if caption:
        st.caption(caption)


def section_title(text: str) -> None:
    st.markdown(f'<div class="section-title">{html_lib.escape(text)}</div>', unsafe_allow_html=True)


def badge_html(text: Any) -> str:
    """Цветной чип категории; цвет детерминированно зависит от текста."""
    text = str(text or "").strip()
    if not text:
        return ""
    tone = int(hashlib.md5(text.encode("utf-8")).hexdigest(), 16) % 8
    return f'<span class="badge tone-{tone}">{html_lib.escape(text)}</span>'


def place_badge(place: str) -> str:
    place = str(place or "").strip()
    return f'<span class="badge-plain">📍 {html_lib.escape(place)}</span>' if place else ""


def stat_grid_html(stats: list[tuple[str, Any, str]]) -> str:
    cards = "".join(
        '<div class="stat-card">'
        f'<div class="stat-icon">{icon}</div>'
        f"<div><div class=\"stat-num\">{html_lib.escape(str(value))}</div>"
        f'<div class="stat-label">{html_lib.escape(label)}</div></div></div>'
        for icon, value, label in stats
    )
    return f'<div class="stat-grid">{cards}</div>'


def empty_state(icon: str, title: str, hint: str, cta_label: str | None = None,
                cta_key: str | None = None, cta_page: "st.Page | None" = None) -> None:
    """Дружелюбное пустое состояние: иконка, подсказка и (опционально) CTA."""
    st.markdown(
        f'<div class="empty-state"><div class="empty-icon">{icon}</div>'
        f'<div class="empty-title">{html_lib.escape(title)}</div>'
        f'<div class="empty-hint">{html_lib.escape(hint)}</div></div>',
        unsafe_allow_html=True,
    )
    if cta_label and cta_page is not None:
        if st.button(cta_label, type="primary", use_container_width=True, key=cta_key):
            st.switch_page(cta_page)


def show_error(exc: Exception) -> None:
    st.error(f"⚠️ {exc}")
