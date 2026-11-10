"""Формы создания ящиков и вещей (переиспользуются несколькими страницами)."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from app.context import get_service
from app.domain.categories import unique_categories
from app.domain.errors import ValidationError
from app.ui.helpers import clear_caches, location_label_map, show_error


NEW_CATEGORY = "__new_category__"  # служебный вариант «создать новую»


def category_options(items: pd.DataFrame) -> list[str]:
    """Общий список категорий: уникальные значения из всех вещей, по алфавиту.

    Делегирует общему алгоритму из домена — тому же, что использует
    ``InventoryService.get_categories``, чтобы список в формах и в сервисе
    совпадал. Дубли пишутся без учёта регистра («инструменты» и
    «Инструменты» — одна категория); каноническим считается первое
    встретившееся написание.
    """
    if items.empty or "Категория" not in items.columns:
        return []
    return unique_categories(items["Категория"].tolist())


def normalize_category(value: str, options: list[str]) -> str:
    """Свободный ввод категории: обрезает пробелы, пустое — «без категории».

    Совпадение с уже существующей категорией без учёта регистра сводится к её
    каноническому написанию, чтобы не плодить дубли вида «инструменты» и
    «Инструменты». Новое имя сохраняется как введено (с обрезкой).
    """
    name = str(value or "").strip()
    if not name:
        return ""
    canonical = {str(option).strip().lower(): str(option).strip() for option in options}
    return canonical.get(name.lower(), name)


def resolve_category(choice: str, new_name: str, options: list[str]) -> str:
    """Итоговое имя категории из состояния пикера (чистая функция — тестируется).

    ``choice`` — значение селекта из :func:`category_picker` (в том числе
    сентинел ``NEW_CATEGORY``), ``new_name`` — текст поля «Название новой
    категории». Пустое имя новой категории — ошибка: вещь не должна молча
    сохраниться «без категории».
    """
    if choice != NEW_CATEGORY:
        return normalize_category(choice, options)
    name = normalize_category(new_name, options)
    if not name:
        raise ValidationError("Укажите название новой категории.")
    return name


def category_picker(form_key: str, current: str = "", options: list[str] | None = None) -> str:
    """Выбор категории из общего списка (общего для всех вещей).

    ВАЖНО: этот пикер нельзя переносить внутрь ``st.form``. Виджеты внутри
    формы не вызывают перезапуск скрипта до нажатия кнопки сабмита, поэтому
    условное поле «Название новой категории» не появилось бы в момент выбора
    «➕ Новая категория…», а после сабмита (``clear_on_submit=True``) введённое
    значение терялось бы. Поэтому пикер рендерится рядом с формой как обычный
    виджет: выбор моментально показывает поле ввода, а итоговое имя вычисляется
    в обработчике сабмита через :func:`resolve_category`.

    Возвращает «сырое» значение селекта: "" — без категории, имя — выбранная
    категория, ``NEW_CATEGORY`` — заведение новой (её имя при сабмите берётся
    из ``st.session_state[f"{form_key}_category_new"]``).
    """
    if options is None:
        options = get_service().get_categories()
    choices = [""] + list(options) + [NEW_CATEGORY]
    default = current if current in options else ""
    choice = st.selectbox(
        "Категория",
        options=choices,
        index=choices.index(default),
        format_func=lambda x: (
            "— без категории —" if x == ""
            else ("➕ Новая категория…" if x == NEW_CATEGORY else x)
        ),
        key=f"{form_key}_category",
        help="Категории общие для всех вещей — выберите из списка или заведите новую.",
    )
    if choice == NEW_CATEGORY:
        initial = current if current and current not in options else ""
        # Поле вне формы: появляется сразу при выборе «➕ Новая категория…»,
        # потому что селект вне формы перезапускает скрипт на каждое изменение.
        st.text_input(
            "Название новой категории",
            value=initial,
            placeholder="Инструменты",
            key=f"{form_key}_category_new",
        )
    return choice


def resolved_category_or_warn(form_key: str, choice: str, options: list[str]) -> str | None:
    """Итоговое имя категории для обработчика сабмита.

    Возвращает имя категории или ``None``, если валидация не прошла
    (предупреждение уже показано пользователю) — в этом случае сохранять
    вещь нельзя.
    """
    try:
        return resolve_category(
            choice,
            st.session_state.get(f"{form_key}_category_new", "") or "",
            options,
        )
    except ValidationError as exc:
        st.warning(str(exc))
        return None


def box_create_form(form_key: str, locations: pd.DataFrame) -> None:
    """Форма создания ящика (используется на страницах «Обзор», «Ящик», «Добавить»)."""
    loc_labels = location_label_map(locations)
    with st.form(form_key, clear_on_submit=True):
        name = st.text_input("Название ящика *", placeholder="Ящик №1 / Коробка «Ёлка»")
        place = st.selectbox(
            "Место хранения",
            options=[""] + list(loc_labels.keys()),
            format_func=lambda x: loc_labels.get(x, "— не указано —"),
        )
        description = st.text_area("Описание", placeholder="Что примерно внутри", height=70)
        if st.form_submit_button("Создать ящик", type="primary", use_container_width=True):
            if not name.strip():
                st.warning("Укажите название ящика.")
            else:
                try:
                    get_service().create_box(name, place, description)
                    clear_caches()
                    place_name = loc_labels.get(place)
                    suffix = f" на месте «{place_name}»" if place_name else ""
                    st.toast(f"Ящик «{name.strip()}» создан{suffix}", icon="📦")
                    st.rerun()
                except Exception as exc:  # noqa: BLE001 — показываем пользователю
                    show_error(exc)


def item_create_form(form_key: str, boxes: pd.DataFrame, labels: dict[str, str]) -> None:
    """Форма добавления вещи (используется на страницах «Добавить» и «Вещи»)."""
    options = get_service().get_categories()
    # Пикер категории — вне формы: внутри st.form выбор «➕ Новая категория…»
    # не показал бы поле ввода до сабмита (см. докстринг category_picker).
    category_choice = category_picker(form_key, options=options)
    with st.form(form_key, clear_on_submit=True):
        name = st.text_input("Название вещи *", placeholder="Отвёртка крестовая")
        box_id = st.selectbox(
            "Ящик *",
            options=list(labels.keys()),
            format_func=lambda x: labels.get(x, x),
        )
        qty = st.number_input("Количество", min_value=1, step=1, value=1)
        notes = st.text_area("Заметки", height=70)
        if st.form_submit_button("Добавить вещь", type="primary", use_container_width=True):
            if not name.strip():
                st.warning("Укажите название вещи.")
            else:
                category = resolved_category_or_warn(form_key, category_choice, options)
                if category is None:
                    return
                try:
                    get_service().create_item(name, box_id, int(qty), category, notes)
                    clear_caches()
                    st.toast(f"«{name.strip()}» добавлена в «{labels[box_id]}»", icon="🗃")
                    st.rerun()
                except Exception as exc:  # noqa: BLE001
                    show_error(exc)
