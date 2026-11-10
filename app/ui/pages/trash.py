"""Корзина: список удалённых сущностей, восстановление, очистка."""

from __future__ import annotations

import html as html_lib
from datetime import datetime

import streamlit as st

from app.context import get_service
from app.domain.errors import StorageError
from app.domain.trash import TRASH_KIND_BOX, TRASH_KIND_ITEM, TRASH_KIND_LOCATION
from app.ui.helpers import clear_caches, empty_state, load_all, page_header, show_error
from app.ui.trash import TRASH_ICONS


def _parent_name(parent_id: str, boxes, locations, trash_entries) -> str | None:
    """Название родителя по ID: среди живых ящиков/мест, затем среди корзины."""
    parent_id = str(parent_id or "")
    if not parent_id:
        return None
    for df in (boxes, locations):
        if df is not None and not df.empty:
            rows = df.loc[df["ID"].astype(str) == parent_id, "Название"]
            if not rows.empty:
                return str(rows.iloc[0])
    for entry in trash_entries:
        if entry.id == parent_id:
            return entry.name
    return None


def _origin_text(entry, boxes, locations, trash_entries) -> str:
    """Откуда удалена запись: «из ящика «X»», «из места «X»» или пусто."""
    if entry.kind == TRASH_KIND_ITEM and entry.parent_id:
        name = _parent_name(entry.parent_id, boxes, locations, trash_entries)
        return f"из ящика «{name}»" if name else "из удалённого ящика"
    if entry.kind == TRASH_KIND_BOX and entry.parent_id:
        name = _parent_name(entry.parent_id, boxes, locations, trash_entries)
        return f"из места «{name}»" if name else "из удалённого места"
    return ""


def page_trash() -> None:
    """Корзина: восстановление отдельных записей и полная очистка."""
    page_header(
        "🗑 Корзина",
        "Удалённые вещи, ящики и места. Записи старше 30 дней удаляются автоматически.",
        page_key="trash",
    )
    service = get_service()
    boxes, _items, locations = load_all()

    # Вычищаем устаревшие записи при каждом открытии страницы.
    try:
        purged = service.purge_expired_trash()
    except Exception as exc:  # noqa: BLE001
        show_error(exc)
        purged = 0
    if purged:
        clear_caches()
        st.caption(f"Очищено устаревших записей: {purged}.")

    try:
        entries = service.trash_entries()
    except StorageError as exc:
        show_error(exc)
        return

    if not entries:
        empty_state(
            "🗑", "Корзина пуста",
            "Удалённые вещи, ящики и места попадают сюда — их можно вернуть.",
        )
        return

    # --- Список записей ----------------------------------------------------- #
    for entry in entries:
        icon = TRASH_ICONS.get(entry.kind, "🗑")
        origin = _origin_text(entry, boxes, locations, entries)
        deleted = str(entry.deleted_at or "").strip()
        when = deleted[:16] if deleted else ""
        with st.container(border=True, key=f"trashrow_{entry.kind}_{entry.id}"):
            left, right = st.columns([0.78, 0.22], vertical_alignment="center")
            with left:
                st.markdown(
                    f'<div class="item-name">{icon} '
                    f"{html_lib.escape(entry.name or entry.id)}</div>",
                    unsafe_allow_html=True,
                )
                meta_bits = []
                if origin:
                    meta_bits.append(html_lib.escape(origin))
                if when:
                    meta_bits.append(f"удалено: {html_lib.escape(when)}")
                st.markdown(
                    f'<div class="item-meta">{" · ".join(meta_bits)}</div>'
                    if meta_bits else "",
                    unsafe_allow_html=True,
                )
            with right:
                if st.button(
                    "Восстановить",
                    key=f"trash_restore_{entry.kind}_{entry.id}",
                    use_container_width=True,
                ):
                    try:
                        name = service.restore(entry.kind, entry.id)
                        clear_caches()
                        st.toast(f"«{name}» восстановлена", icon="↩️")
                        st.rerun()
                    except Exception as exc:  # noqa: BLE001
                        show_error(exc)

    # --- Очистка корзины (двухшаговое подтверждение) ------------------------- #
    st.divider()
    if st.button("🧹 Очистить корзину", key="trash_clear_button"):
        st.session_state["trash_clear_confirm"] = True
        st.rerun()
    if st.session_state.get("trash_clear_confirm"):
        st.warning(
            f"Удалить из корзины все {len(entries)} записей без возможности "
            "восстановления?"
        )
        confirm_col, cancel_col = st.columns(2)
        with confirm_col:
            if st.button("Да, очистить", type="primary", use_container_width=True,
                         key="trash_clear_yes"):
                try:
                    count = service.clear_trash()
                    clear_caches()
                except Exception as exc:  # noqa: BLE001
                    show_error(exc)
                else:
                    st.session_state.pop("trash_clear_confirm", None)
                    st.toast(f"Корзина очищена: {count}", icon="🧹")
                    st.rerun()
        with cancel_col:
            if st.button("Отмена", use_container_width=True, key="trash_clear_no"):
                st.session_state.pop("trash_clear_confirm", None)
                st.rerun()
