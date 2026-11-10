"""Добавить: новый ящик или новая вещь."""

from __future__ import annotations

import streamlit as st

from app.ui.forms import box_create_form, item_create_form
from app.ui.helpers import box_label_map, empty_state, load_all, page_header
from app.ui.registry import PAGES


def page_add() -> None:
    boxes, items, locations = load_all()
    page_header("➕ Добавить", page_key="add")

    mode = st.segmented_control(
        "Что добавляем",
        options=["Новый ящик", "Новая вещь"],
        default="Новый ящик",
        key="add_mode",
        label_visibility="collapsed",
    )
    if mode is None:
        mode = "Новый ящик"

    if mode == "Новый ящик":
        box_create_form("form_add_box", locations)
    else:
        if boxes.empty:
            empty_state(
                "📦", "Сначала создайте ящик",
                "Вещи хранятся в ящиках — создайте хотя бы один.",
                cta_label="Перейти к «Новый ящик»", cta_key="add_cta_box",
            )
            if st.button("Создать ящик", type="primary", use_container_width=True, key="add_cta_box_btn"):
                st.session_state["add_mode"] = "Новый ящик"
                st.rerun()
        else:
            item_create_form("form_add_item", boxes, box_label_map(boxes, locations))
