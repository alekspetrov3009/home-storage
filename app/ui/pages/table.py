"""Вещи: редактор таблицы с массовой правкой."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from app.context import get_service
from app.domain.fields import ITEM_FIELDS, now_str
from app.domain.ids import new_id
from app.ui.forms import item_create_form, normalize_category
from app.ui.helpers import (
    box_label_map,
    clean_id,
    clean_text,
    empty_state,
    item_row_changed,
    load_all,
    page_header,
    show_error,
    clear_caches,
    to_qty,
)
from app.ui.registry import PAGES
from app.ui.trash import NO_BOX_LABEL, remember_deleted


def page_table() -> None:
    """Вещи: таблица с массовой правкой плюс быстрое добавление и удаление."""
    boxes, items, locations = load_all()
    page_header(
        "📋 Вещи",
        "Массовое редактирование: правьте ячейки и сохраните изменения.",
        page_key="table",
    )

    labels = box_label_map(boxes, locations)

    if boxes.empty:
        empty_state(
            "📦", "Сначала создайте ящик",
            "Вещи хранятся в ящиках — создайте хотя бы один.",
            cta_label="Добавить первый ящик", cta_key="table_cta_add", cta_page=PAGES.get("add"),
        )
        return

    if items.empty:
        empty_state(
            "🗃", "Вещей пока нет",
            "Добавьте первую вещь — она появится в таблице.",
            cta_label="Добавить вещь", cta_key="table_cta_item", cta_page=PAGES.get("add"),
        )
        return

    # --- Быстрое добавление ------------------------------------------------- #
    with st.expander("➕ Добавить вещь"):
        item_create_form("form_table_add", boxes, labels)

    # --- Фильтр + счётчик найденного ----------------------------------------- #
    st.markdown(
        '<div class="chip-hint">💡 Правьте ячейки и нажмите «Сохранить». Галочка '
        "в колонке «Удалить» отправляет строку в корзину; новые строки — внизу "
        "таблицы. При активном фильтре скрытые строки остаются без изменений.</div>",
        unsafe_allow_html=True,
    )
    filter_col, count_col = st.columns([0.78, 0.22], vertical_alignment="center")
    with filter_col:
        filter_q = st.text_input(
            "Фильтр по названию, категории, заметкам или ящику",
            placeholder="Например: инструменты",
            label_visibility="collapsed",
            key="table_filter",
        ).strip().lower()

    editable = items.copy()
    if filter_q:
        haystack = (
            editable["Название"].astype(str).str.lower()
            + " " + editable["Категория"].astype(str).str.lower()
            + " " + editable["Заметки"].astype(str).str.lower()
            + " " + editable["Ящик_ID"].map(labels).fillna("").astype(str).str.lower()
        )
        editable = editable[haystack.str.contains(filter_q, regex=False)]

    with count_col:
        st.markdown(f'<div class="chip-count">{len(editable)} найдено</div>', unsafe_allow_html=True)

    if editable.empty:
        empty_state("🔍", "Ничего не найдено", "Попробуйте изменить фильтр.")
        return

    editable["Ящик"] = editable["Ящик_ID"].map(labels).fillna(NO_BOX_LABEL)
    editable["Количество"] = pd.to_numeric(editable["Количество"], errors="coerce").fillna(0).astype(int)

    display = editable[["ID", "Название", "Ящик", "Количество", "Категория", "Заметки"]].copy()
    display["Удалить"] = False

    edited = st.data_editor(
        display,
        key="items_editor",
        use_container_width=True,
        hide_index=True,
        num_rows="dynamic",
        height=min(620, 220 + 35 * len(display)),
        column_config={
            "ID": None,  # служебная колонка, не показываем
            "Название": st.column_config.TextColumn("Название", required=True, width="medium"),
            "Ящик": st.column_config.SelectboxColumn(
                "Ящик", options=list(labels.values()) + [NO_BOX_LABEL], required=True, width="medium"
            ),
            "Количество": st.column_config.NumberColumn("Кол-во", min_value=0, step=1, width="small"),
            "Категория": st.column_config.TextColumn(
                "Категория",
                help="Свободный ввод: можно завести новую категорию",
                width="small",
            ),
            "Заметки": st.column_config.TextColumn("Заметки", width="medium"),
            "Удалить": st.column_config.CheckboxColumn(
                "Удалить",
                help="Отметьте, чтобы убрать строку в корзину при сохранении",
                default=False,
                width="small",
            ),
        },
    )

    with st.container(border=True, key="table_save_panel"):
        save_clicked = st.button(
            "💾 Сохранить", type="primary", use_container_width=True, key="table_save_button"
        )

    if save_clicked:
        try:
            label_to_id = {label: box_id for box_id, label in labels.items()}
            known_categories = get_service().get_categories()
            originals = {str(row["ID"]): row for _, row in items.iterrows()}
            rows = []
            deleted_ids: list[str] = []
            deleted_names: list[str] = []
            for _, row in edited.iterrows():
                name = clean_text(row.get("Название"))
                if not name:
                    continue  # пустые строки, добавленные редактором, пропускаем
                row_id = clean_id(row.get("ID"))
                if bool(row.get("Удалить", False)):
                    deleted_names.append(name)
                    if row_id:
                        deleted_ids.append(row_id)  # отмеченные строки убираются в корзину
                    continue
                box_label = clean_text(row.get("Ящик"))
                if box_label == NO_BOX_LABEL:
                    # Вещь без ящика (например, её ящик лежит в корзине):
                    # сохраняем прежнюю привязку, чтобы восстановление ящика
                    # вернуло вещь на место.
                    previous = items.loc[items["ID"].astype(str) == row_id, "Ящик_ID"]
                    box_id = str(previous.iloc[0]) if not previous.empty else ""
                else:
                    box_id = label_to_id.get(box_label, "")
                if not box_id:
                    st.warning(f"Для «{name}» не выбран ящик — строка пропущена.")
                    continue
                values = {
                    "Название": name,
                    "Ящик_ID": box_id,
                    "Количество": to_qty(row.get("Количество", 0)),
                    # Категория — свободный ввод: обрезаем пробелы и сводим
                    # к каноническому написанию уже существующей категории.
                    "Категория": normalize_category(
                        clean_text(row.get("Категория")), known_categories
                    ),
                    "Заметки": clean_text(row.get("Заметки")),
                }
                original = originals.get(row_id)
                # «Обновлён» проставляется только фактически изменённым и новым
                # строкам: иначе каждая перезапись фильтра обновляла отметку
                # всем строкам, и «Недавно обновлённое» теряло смысл.
                if original is not None and not item_row_changed(
                    original, values, known_categories
                ):
                    updated = clean_text(original.get("Обновлён")) or now_str()
                else:
                    updated = now_str()
                rows.append(
                    {
                        "ID": row_id or new_id(),
                        "Название": values["Название"],
                        "Ящик_ID": values["Ящик_ID"],
                        "Количество": values["Количество"],
                        "Категория": values["Категория"],
                        "Заметки": values["Заметки"],
                        "Обновлён": updated,
                    }
                )

            # При активном фильтре строки, скрытые фильтром, не показывались
            # в редакторе — сохраняем их как есть, чтобы не потерять данные.
            # Строки, отмеченные на удаление, сюда не попадают.
            kept_ids = {str(r["ID"]) for r in rows} | set(deleted_ids)
            preserved = items[~items["ID"].astype(str).isin(kept_ids)]
            for _, row in preserved.iterrows():
                rows.append(
                    {
                        "ID": str(row["ID"]),
                        "Название": str(row["Название"]),
                        "Ящик_ID": str(row["Ящик_ID"]),
                        "Количество": to_qty(row["Количество"]),
                        "Категория": str(row["Категория"]),
                        "Заметки": str(row["Заметки"]),
                        "Обновлён": str(row["Обновлён"]) or now_str(),
                    }
                )

            # Сначала убираем отмеченные строки в корзину, затем перезаписываем
            # лист «Вещи» оставшимися строками.
            deleted_entries = []
            if deleted_ids:
                deleted_entries = get_service().delete_items(deleted_ids)
                remember_deleted(deleted_entries, "table")
            get_service().replace_items(pd.DataFrame(rows, columns=ITEM_FIELDS))
            clear_caches()
            message = f"Сохранено строк: {len(rows)}."
            if deleted_names:
                message += f" В корзину: {len(deleted_names)} ({', '.join(deleted_names)})."
            st.toast(message, icon="💾")
            st.rerun()
        except Exception as exc:  # noqa: BLE001
            show_error(exc)
