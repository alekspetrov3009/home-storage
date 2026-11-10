"""Сборка и запуск интерфейса: навигация, боковая панель, точка входа UI."""

from __future__ import annotations

import os

import streamlit as st

from app.config import get_config
from app.context import get_service
from app.ui.helpers import clear_caches, load_all, show_error
from app.ui.pages.add import page_add
from app.ui.pages.box_view import page_box_view
from app.ui.pages.dashboard import page_dashboard
from app.ui.pages.edit import page_edit
from app.ui.pages.locations import page_locations
from app.ui.pages.search import page_search
from app.ui.pages.table import page_table
from app.ui.pages.trash import page_trash
from app.ui.registry import PAGES
from app.ui.styles import brand_html, inject_css, theme_toggle


def run() -> None:
    """Точка входа интерфейса. Запускается как ``streamlit run main.py``."""
    st.set_page_config(
        page_title="Домашний склад",
        page_icon="📦",
        layout="wide",
        initial_sidebar_state="auto",
    )

    theme = inject_css()

    # Проверяем хранилище до первой навигации: при поломанном файле показываем
    # ошибку вместо пустого интерфейса.
    load_all()

    pages = [
        st.Page(page_dashboard, title="Обзор", icon=":material/dashboard:", default=True),
        st.Page(page_search, title="Поиск", icon=":material/search:"),
        st.Page(page_box_view, title="Ящик", icon=":material/inventory_2:", url_path="box"),
        st.Page(page_table, title="Вещи", icon=":material/list_alt:", url_path="items"),
        st.Page(page_add, title="Добавить", icon=":material/add_circle:", url_path="add"),
        st.Page(page_edit, title="Редактировать", icon=":material/edit_note:", url_path="edit"),
        st.Page(page_locations, title="Места", icon=":material/place:", url_path="places"),
        st.Page(page_trash, title="Корзина", icon=":material/delete:", url_path="trash"),
    ]
    PAGES.clear()
    PAGES.update({
        "box": pages[2],
        "add": pages[4],
    })

    with st.sidebar:
        brand_html()

    nav = st.navigation(pages)

    with st.sidebar:
        theme_toggle(theme)
        st.markdown('<div class="side-section">Данные</div>', unsafe_allow_html=True)
        # Tertiary-кнопки в один ряд: компактная секция без «лапши».
        refresh_col, backup_col = st.columns(2, gap="small")
        with refresh_col:
            if st.button("🔄 Обновить", type="tertiary", use_container_width=True,
                         key="refresh_button", help="Перечитать файл данных"):
                clear_caches()
                st.toast("Данные обновлены", icon="🔄")
                st.rerun()
        with backup_col:
            if st.button("💾 Копия", type="tertiary", use_container_width=True,
                         key="backup_button", help="Сохранить резервную копию файла"):
                try:
                    path = get_service().backup_file()
                    st.toast(f"Копия создана: {os.path.basename(path)}", icon="💾")
                except Exception as exc:  # noqa: BLE001
                    show_error(exc)
        st.caption(f"Файл: `{get_config().data_file}`")

    nav.run()
