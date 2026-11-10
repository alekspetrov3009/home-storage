"""Корзина: полоса отмены удаления и общие константы UI.

Единый механизм отмены для всех страниц: удаление запоминает запись в
session_state (``remember_deleted``), а ``render_undo_strip`` рисует вверху
страницы компактную полосу «Только что удалено: … [Отменить]». st.toast не
подходит для кнопки отмены — у него нет action-кнопок, поэтому аффорданс
живёт на самой странице. Полоса исчезает при переходе на другую страницу,
через 30 секунд или при новом удалении.
"""

from __future__ import annotations

import html as html_lib
import time

import streamlit as st

from app.context import get_service
from app.domain.errors import StorageError
from app.ui.helpers import clear_caches, show_error

# Ключ session_state с последним удалением (для полосы отмены).
UNDO_KEY = "undo_pending"

# Сколько секунд полоса отмены остаётся на странице.
UNDO_TTL_SECONDS = 30

# Иконки записей корзины по типу (колонка «Тип» листа «Корзина»).
TRASH_ICONS = {"вещь": "🗃", "ящик": "📦", "место": "🗺"}

# Подписи отсутствующих родителей.
NO_BOX_LABEL = "— без ящика —"
NO_LOCATION_LABEL = "— без места хранения —"


def remember_deleted(entries, page_key: str) -> None:
    """Запоминает только что удалённые записи для полосы отмены.

    Новое удаление вытесняет прежнее: отменить можно только последнее
    действие, как и обещает подпись полосы.
    """
    st.session_state[UNDO_KEY] = {
        "entries": [(e.kind, e.id, e.name) for e in entries],
        "ts": time.time(),
        "page": page_key,
    }


def _undo_label(state: dict) -> str:
    names = [str(label) for _, _, label in state["entries"]]
    if len(names) == 1:
        return f"«{names[0]}»"
    preview = ", ".join(f"«{n}»" for n in names[:3])
    more = f" и ещё {len(names) - 3}" if len(names) > 3 else ""
    return f"{len(names)} записей: {preview}{more}"


def render_undo_strip(page_key: str) -> None:
    """Полоса «Только что удалено: … [Отменить]» вверху текущей страницы.

    Вызывается из page_header каждой страницы. Запоминает ключ страницы,
    чтобы карточки вещей могли привязать своё удаление к правильной странице.
    """
    st.session_state["_page_key"] = page_key

    state = st.session_state.get(UNDO_KEY)
    if not state:
        return
    expired = time.time() - float(state.get("ts", 0)) > UNDO_TTL_SECONDS
    if expired or state.get("page") != page_key:
        # Истёк срок или пользователь ушёл на другую страницу — прячем полосу.
        st.session_state.pop(UNDO_KEY, None)
        return

    label = _undo_label(state)
    with st.container(border=True, key="undo_strip"):
        left, right = st.columns([0.82, 0.18], vertical_alignment="center")
        with left:
            st.markdown(
                '<div class="item-meta">🗑 Только что удалено: '
                f"{html_lib.escape(label)}. Запись можно вернуть.</div>",
                unsafe_allow_html=True,
            )
        with right:
            if st.button("↩️ Отменить", key="undo_strip_button", use_container_width=True):
                try:
                    restored, skipped = 0, 0
                    for kind, entity_id, _name in state["entries"]:
                        try:
                            get_service().restore(kind, entity_id)
                            restored += 1
                        except StorageError as exc:
                            if "не найдена в корзине" in str(exc):
                                # Запись уже восстановили в другой вкладке —
                                # это не сбой отмены, считаем пропущенной.
                                skipped += 1
                            else:
                                raise
                    clear_caches()
                    st.session_state.pop(UNDO_KEY, None)
                    message = f"Восстановлено: {restored}"
                    if skipped:
                        message += f", пропущено: {skipped}"
                    st.toast(message, icon="↩️")
                    st.rerun()
                except Exception as exc:  # noqa: BLE001
                    show_error(exc)
