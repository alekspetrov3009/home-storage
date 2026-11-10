"""Обзор: статистика, быстрый поиск, ящики и последние обновления."""

from __future__ import annotations

import html as html_lib

import streamlit as st

from app.context import get_service
from app.ui.helpers import (
    box_label_map,
    empty_state,
    load_all,
    location_label_map,
    page_header,
    place_badge,
    qty_total,
    section_title,
    stat_grid_html,
)
from app.ui.item_cards import render_item_list
from app.ui.trash import NO_LOCATION_LABEL
from app.ui.registry import PAGES


def page_dashboard() -> None:
    """Обзор: статистика, быстрый поиск, ящики и последние обновления."""
    boxes, items, locations = load_all()
    # Глубокая ссылка из старых QR-кодов: /?box=<id> -> страница «Ящик».
    requested = st.query_params.get("box")
    if requested:
        if requested in boxes["ID"].astype(str).values:
            # switch_page останавливает выполнение скрипта, поэтому pop после
            # него недостижим: параметр ?box= снимает сама страница «Ящик».
            st.switch_page(PAGES["box"])
        # Битая или устаревшая ссылка — не выходим, а рисуем обычный Обзор.
        st.query_params.pop("box")
        st.warning("Ссылка указывает на несуществующий ящик — показан общий обзор.")

    stamps = [s for s in items["Обновлён"].astype(str).tolist() + boxes["Создан"].astype(str).tolist()
              if str(s).strip()]
    caption = f"Последнее обновление: {max(stamps)}" if stamps else "Записей пока нет"
    page_header("Обзор", caption, page_key="dashboard")

    total_units = qty_total(items)
    st.markdown(stat_grid_html([
        ("📦", len(boxes), "ящиков"),
        ("🗃", len(items), "позиций"),
        ("🔢", total_units, "единиц всего"),
        ("🗺", len(locations), "мест хранения"),
    ]), unsafe_allow_html=True)

    if boxes.empty and items.empty:
        empty_state(
            "📦", "Начните с первого ящика",
            "Создайте ящик, положите в него вещи — и они появятся здесь.",
            cta_label="Добавить первый ящик", cta_key="dash_cta_box", cta_page=PAGES.get("add"),
        )
        return

    labels = box_label_map(boxes, locations)
    loc_names = location_label_map(locations)

    # --- Быстрый поиск ------------------------------------------------------ #
    section_title("Быстрый поиск")
    query = st.text_input(
        "Что ищем?",
        placeholder="Например: отвёртка, гирлянда, паспорт…",
        label_visibility="collapsed",
        key="dash_query",
    ).strip().lower()
    if query:
        ids = get_service().search_item_ids(items, labels, query)
        st.caption(f"Найдено: {len(ids)}")
        render_item_list(ids, labels, key_prefix="dash_q", allow_delete=True,
                         empty_hint="Ничего не найдено. Попробуйте другой запрос.")
        return

    # --- Ящики -------------------------------------------------------------- #
    if not boxes.empty:
        section_title("Ящики")
        for _, box in boxes.sort_values("Название").iterrows():
            box_id = str(box["ID"])
            inside = items[items["Ящик_ID"].astype(str) == box_id]
            units = qty_total(inside)
            with st.container(border=True, key=f"boxcard_{box_id}"):
                left, right = st.columns([0.72, 0.28], vertical_alignment="center", wrap=True)
                with left:
                    st.markdown(
                        f'<div class="item-name">📦 {html_lib.escape(str(box["Название"]))}</div>',
                        unsafe_allow_html=True,
                    )
                    place = loc_names.get(str(box["Место_ID"]), "")
                    place_html = place_badge(place) or f'<span class="badge-plain">{NO_LOCATION_LABEL}</span>'
                    st.markdown(
                        place_html + f'<div class="item-meta">{len(inside)} поз. · {units} ед.</div>',
                        unsafe_allow_html=True,
                    )
                with right:
                    if st.button("Открыть →", key=f"dash_open_{box_id}", use_container_width=True):
                        st.query_params["box"] = box_id
                        st.switch_page(PAGES["box"])

    # --- Недавно обновлённое ------------------------------------------------ #
    if not items.empty:
        section_title("Недавно обновлённое")
        recent = items.sort_values("Обновлён", ascending=False).head(5)
        render_item_list(recent["ID"].astype(str).tolist(), labels,
                         key_prefix="dash_recent", allow_delete=True)
