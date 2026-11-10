"""Поиск: глобальный поиск по вещам."""

from __future__ import annotations

import streamlit as st

from app.context import get_service
from app.ui.helpers import box_label_map, load_all, page_header
from app.ui.item_cards import render_item_list


def page_search() -> None:
    boxes, items, locations = load_all()
    page_header("🔍 Поиск вещей", "По названию, категории, заметкам и названию ящика", page_key="search")

    query = st.text_input(
        "Что ищем?",
        placeholder="Например: отвёртка, гирлянда, паспорт…",
        label_visibility="collapsed",
        key="search_query",
    ).strip().lower()

    labels = box_label_map(boxes, locations)
    if query:
        ids = get_service().search_item_ids(items, labels, query)
        st.caption(f"Найдено: {len(ids)}")
        render_item_list(ids, labels, key_prefix="search", allow_delete=True,
                         empty_hint="Ничего не найдено. Попробуйте другой запрос.")
    else:
        st.caption("Введите запрос или оставьте поле пустым, чтобы увидеть все вещи.")
        render_item_list(items["ID"].astype(str).tolist(), labels, key_prefix="search",
                         allow_delete=True)
