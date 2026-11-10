"""Редактировать: количество, перенос, поля, удаление ящика."""

from __future__ import annotations

import streamlit as st

from app.context import get_service
from app.ui.forms import category_picker, resolved_category_or_warn
from app.ui.helpers import (
    box_label_map,
    empty_state,
    load_all,
    page_header,
    section_title,
    show_error,
    clear_caches,
    to_qty,
)
from app.ui.trash import NO_BOX_LABEL, remember_deleted
from app.ui.registry import PAGES


def page_edit() -> None:
    boxes, items, locations = load_all()
    page_header("✏️ Редактировать", page_key="edit")

    if items.empty:
        empty_state(
            "🗃", "Список вещей пуст", "Редактировать пока нечего — добавьте вещи.",
            cta_label="Добавить вещь", cta_key="edit_cta_add", cta_page=PAGES.get("add"),
        )
        return

    labels = box_label_map(boxes, locations)
    item_ids = items["ID"].astype(str).tolist()

    def _item_label(item_id: str) -> str:
        """Подпись вещи для выпадающего списка.

        Устойчива к неизвестному ID: Streamlit может вызвать format_func
        для значения, которого уже нет в списке (например, после удаления).
        """
        rows = items.loc[items["ID"].astype(str) == str(item_id)]
        if rows.empty:
            return str(item_id)
        row = rows.iloc[0]
        return f"{row['Название']} → {labels.get(str(row['Ящик_ID']), NO_BOX_LABEL)}"

    selected_id = st.selectbox(
        "Выберите вещь",
        options=item_ids,
        format_func=_item_label,
        key="edit_item_select",
    )
    matches = items[items["ID"] == selected_id]
    if matches.empty:
        # Кэш мог протухнуть между чтением списка и рендером (параллельная
        # запись в другом потоке, выбор указывает на исчезнувшую вещь) —
        # берём первую доступную вместо IndexError.
        matches = items
    item = matches.iloc[0]
    selected_id = str(item["ID"])
    current_qty = to_qty(item["Количество"])
    current_box = str(item["Ящик_ID"])

    # --- Количество -------------------------------------------------------- #
    section_title("Количество")
    with st.container(border=True, key="qty_card"):
        c_minus, c_value, c_plus = st.columns([1, 1, 1], wrap=True)
        with c_minus:
            if st.button("➖", use_container_width=True, key="qty_minus",
                         disabled=current_qty <= 0):
                try:
                    get_service().update_item(selected_id, {"Количество": current_qty - 1})
                    clear_caches()
                    st.toast("Количество обновлено", icon="✅")
                    st.rerun()
                except Exception as exc:  # noqa: BLE001
                    show_error(exc)
        with c_value:
            st.markdown(f'<div class="qty-display" style="font-size:1.9rem">{current_qty}</div>',
                        unsafe_allow_html=True)
        with c_plus:
            if st.button("➕", use_container_width=True, key="qty_plus"):
                try:
                    get_service().update_item(selected_id, {"Количество": current_qty + 1})
                    clear_caches()
                    st.toast("Количество обновлено", icon="✅")
                    st.rerun()
                except Exception as exc:  # noqa: BLE001
                    show_error(exc)

    with st.form("form_set_qty"):
        new_qty = st.number_input("Задать точное количество", min_value=0, step=1, value=current_qty)
        if st.form_submit_button("Сохранить количество", use_container_width=True):
            if int(new_qty) == current_qty:
                st.toast("Количество не изменилось", icon="ℹ️")
            else:
                try:
                    get_service().update_item(selected_id, {"Количество": int(new_qty)})
                    clear_caches()
                    st.toast("Количество обновлено", icon="✅")
                    st.rerun()
                except Exception as exc:  # noqa: BLE001
                    show_error(exc)

    # --- Перенос в другой ящик --------------------------------------------- #
    section_title("Перенести в другой ящик")
    if boxes.empty:
        st.caption("Нет доступных ящиков.")
    else:
        options = [b for b in labels.keys() if b != current_box] or list(labels.keys())
        target = st.selectbox(
            "Целевой ящик",
            options=options,
            format_func=lambda x: labels.get(x, x),
            key="move_target",
        )
        if st.button("📦 Перенести", use_container_width=True, disabled=target == current_box, key="move_button"):
            try:
                get_service().move_item(selected_id, target)
                clear_caches()
                st.toast(f"Перенесено в «{labels[target]}»", icon="📦")
                st.rerun()
            except Exception as exc:  # noqa: BLE001
                show_error(exc)

    # --- Редактирование полей ---------------------------------------------- #
    section_title("Название / категория / заметки")
    with st.expander("Изменить поля вещи"):
        category_options_list = get_service().get_categories()
        # Пикер категории — вне формы: внутри st.form выбор «➕ Новая категория…»
        # не показал бы поле ввода до сабмита (см. докстринг category_picker).
        category_choice = category_picker(
            "form_edit_fields", current=str(item["Категория"]), options=category_options_list
        )
        with st.form("form_edit_fields"):
            new_name = st.text_input("Название", value=str(item["Название"]))
            new_notes = st.text_area("Заметки", value=str(item["Заметки"]), height=80)
            if st.form_submit_button("Сохранить", type="primary", use_container_width=True):
                if not new_name.strip():
                    st.warning("Название не может быть пустым.")
                else:
                    new_category = resolved_category_or_warn(
                        "form_edit_fields", category_choice, category_options_list
                    )
                    if new_category is not None:
                        try:
                            get_service().update_item(
                                selected_id,
                                {
                                    "Название": new_name.strip(),
                                    "Категория": new_category,
                                    "Заметки": new_notes.strip(),
                                },
                            )
                            clear_caches()
                            st.toast("Изменения сохранены", icon="✅")
                            st.rerun()
                        except Exception as exc:  # noqa: BLE001
                            show_error(exc)

    # --- Удаление ящика ------------------------------------------------------ #
    if not boxes.empty:
        section_title("Удалить ящик")
        with st.expander("🗑 Удалить ящик"):
            st.caption(
                "Ящик переедет в корзину, откуда его можно вернуть. Вещи из ящика "
                "останутся и будут показываться как «— без ящика —»; восстановление "
                "ящика вернёт их на место."
            )
            box_to_delete = st.selectbox(
                "Ящик",
                options=list(labels.keys()),
                format_func=lambda x: labels.get(x, x),
                key="delete_box_select",
            )
            if st.button("Удалить ящик", use_container_width=True, key="delete_box_button"):
                try:
                    entry = get_service().delete_box(box_to_delete)
                    clear_caches()
                    remember_deleted([entry], "edit")
                    st.toast(f"Ящик «{entry.name}» удалён — можно отменить", icon="🗑")
                    st.rerun()
                except Exception as exc:  # noqa: BLE001
                    show_error(exc)
