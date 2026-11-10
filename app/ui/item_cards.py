"""Карточки вещей: степперы количества, удаление, фрагменты Streamlit."""

from __future__ import annotations

import html as html_lib

import pandas as pd
import streamlit as st

from app.context import get_service
from app.ui.helpers import badge_html, empty_state, section_title, show_error, to_qty, qty_total
from app.ui.trash import NO_BOX_LABEL, remember_deleted


def _change_qty(item_id: str, new_qty: int, current_qty: int) -> None:
    """Меняет количество вещи. Вызывается только внутри фрагментов."""
    new_qty = max(0, int(new_qty))
    if new_qty == current_qty:
        # Например, «−» при нуле: холостая запись дала бы ложный тост
        # «Количество обновлено» без фактического изменения.
        return
    try:
        get_service().update_item(item_id, {"Количество": new_qty})
        get_service().clear_cache()
        st.toast("Количество обновлено", icon="✅")
        st.rerun(scope="fragment")
    except Exception as exc:  # noqa: BLE001
        show_error(exc)


def _delete_item(item_id: str, name: str) -> None:
    try:
        entry = get_service().delete_item(item_id)
        get_service().clear_cache()
        remember_deleted([entry], st.session_state.get("_page_key", ""))
        st.toast(f"«{name}» удалена — можно отменить", icon="🗑")
        # Полный rerun: полоса отмены живёт на странице, вне фрагмента.
        st.rerun()
    except Exception as exc:  # noqa: BLE001
        show_error(exc)


def item_card(item: pd.Series, labels: dict[str, str], key_prefix: str,
              allow_delete: bool = False) -> None:
    """Карточка вещи: название, чип категории, ящик, заметки и степпер «−/+»."""
    box_name = labels.get(str(item["Ящик_ID"]), NO_BOX_LABEL)
    qty = to_qty(item["Количество"])
    item_id = str(item["ID"])
    with st.container(border=True, key=f"itemcard_{key_prefix}"):
        top, controls = st.columns([0.68, 0.32], vertical_alignment="center", wrap=True)
        with top:
            st.markdown(
                f'<div class="item-name">{html_lib.escape(str(item["Название"]))}</div>',
                unsafe_allow_html=True,
            )
            meta = f'📦 {html_lib.escape(box_name)}'
            notes = str(item.get("Заметки", "") or "").strip()
            if notes:
                meta += f' &nbsp;·&nbsp; 📝 {html_lib.escape(notes)}'
            st.markdown(
                badge_html(item.get("Категория", "")) + f'<div class="item-meta">{meta}</div>',
                unsafe_allow_html=True,
            )
        with controls:
            if allow_delete:
                c1, c2, c3, c4 = st.columns([1, 1.1, 1, 0.9], vertical_alignment="center",
                                            gap="small", wrap=True)
            else:
                c1, c2, c3 = st.columns([1, 1.1, 1], vertical_alignment="center",
                                        gap="small", wrap=True)
            with c1:
                if st.button("−", key=f"{key_prefix}_dec", use_container_width=True,
                             disabled=qty <= 0, help="Убавить количество"):
                    _change_qty(item_id, qty - 1, qty)
            with c2:
                st.markdown(f'<div class="qty-display">{qty}</div>', unsafe_allow_html=True)
            with c3:
                if st.button("+", key=f"{key_prefix}_inc", use_container_width=True,
                             help="Прибавить количество"):
                    _change_qty(item_id, qty + 1, qty)
            if allow_delete:
                with c4:
                    with st.popover("🗑", use_container_width=True):
                        st.caption(
                            f"Удалить «{item['Название']}»? Вещь переедет в корзину, "
                            "её можно будет вернуть."
                        )
                        if st.button("Удалить", key=f"{key_prefix}_del_btn", type="primary",
                                     use_container_width=True):
                            _delete_item(item_id, str(item["Название"]))


@st.fragment
def render_item_list(item_ids: list[str], labels: dict[str, str], key_prefix: str,
                     allow_delete: bool = False, empty_hint: str = "Добавьте вещи, чтобы они появились здесь.") -> None:
    """Список карточек вещей. Фрагмент: клики по степперам и удалению
    перерисовывают только список, а не всю страницу."""
    items = get_service().load_items()
    if item_ids:
        items = items[items["ID"].astype(str).isin(item_ids)]
    else:
        items = items.iloc[0:0]
    if items.empty:
        empty_state("🗂", "Здесь пока пусто", empty_hint)
        return
    for _, item in items.sort_values("Название").iterrows():
        item_card(item, labels, key_prefix=f"{key_prefix}_{item['ID']}", allow_delete=allow_delete)


@st.fragment
def render_box_contents(box_id: str, labels: dict[str, str]) -> None:
    """Содержимое ящика. Фрагмент: степперы количества не перерисовывают
    всю страницу, итоги пересчитываются сразу."""
    items = get_service().load_items()
    inside = items[items["Ящик_ID"].astype(str) == str(box_id)]
    total = qty_total(inside)
    section_title(f"В ящике · {len(inside)} поз. · {total} ед.")
    if inside.empty:
        empty_state("🗃", "Ящик пуст", "Добавьте вещь на странице «Добавить» или во вкладке «Вещи».")
        return
    for _, item in inside.sort_values("Название").iterrows():
        item_card(item, labels, key_prefix=f"boxc_{item['ID']}", allow_delete=True)
