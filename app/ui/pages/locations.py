"""Места: управление местами хранения."""

from __future__ import annotations

import html as html_lib

import streamlit as st

from app.context import get_service
from app.ui.helpers import clear_caches, empty_state, load_all, page_header, show_error
from app.ui.trash import remember_deleted


def page_locations() -> None:
    """Управление местами хранения: комнаты, полки, шкафы."""
    boxes, items, locations = load_all()
    page_header("🗺 Места хранения", "Полки, комнаты, шкафы… Ящики привязываются к местам при создании.", page_key="places")

    with st.expander("➕ Новое место", expanded=locations.empty):
        with st.form("form_add_location", clear_on_submit=True):
            name = st.text_input("Название места *", placeholder="Гараж, полка 2 / Балкон")
            description = st.text_area("Описание", height=70)
            if st.form_submit_button("Создать место", type="primary", use_container_width=True):
                if not name.strip():
                    st.warning("Укажите название места.")
                else:
                    try:
                        get_service().create_location(name, description)
                        clear_caches()
                        st.toast(f"Место «{name.strip()}» создано", icon="🗺")
                        st.rerun()
                    except Exception as exc:  # noqa: BLE001
                        show_error(exc)

    if locations.empty:
        empty_state("🗺", "Мест хранения пока нет", "Место — это комната, полка или шкаф, где стоят ящики.")
        return

    for _, loc in locations.sort_values("Название").iterrows():
        loc_id = str(loc["ID"])
        linked = int((boxes["Место_ID"] == loc_id).sum()) if not boxes.empty else 0
        with st.container(border=True, key=f"loccard_{loc_id}"):
            left, right = st.columns([0.7, 0.3], vertical_alignment="center")
            with left:
                st.markdown(
                    f'<div class="item-name">🗺 {html_lib.escape(str(loc["Название"]))}</div>',
                    unsafe_allow_html=True,
                )
                meta = f'📦 Привязано ящиков: {linked}'
                if loc["Описание"]:
                    meta = f'ℹ️ {html_lib.escape(str(loc["Описание"]))} &nbsp;·&nbsp; {meta}'
                st.markdown(f'<div class="item-meta">{meta}</div>', unsafe_allow_html=True)
            with right:
                if st.button(
                    "🗑 Удалить",
                    key=f"del_loc_{loc_id}",
                    use_container_width=True,
                    help="Место переедет в корзину; ящики останутся без места хранения." if linked else None,
                ):
                    try:
                        entry = get_service().delete_location(loc_id)
                        clear_caches()
                        remember_deleted([entry], "places")
                        st.toast(f"Место «{loc['Название']}» удалено — можно отменить", icon="🗑")
                        st.rerun()
                    except Exception as exc:  # noqa: BLE001
                        show_error(exc)
