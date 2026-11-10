"""Тесты чистых хелперов данных: NaN-безопасная очистка ячеек, суммы, подписи.

Функции импортируются из ``app.helpers`` и не требуют транспортного слоя:
редактор таблицы даёт NaN в каждой колонке новых строк, а вручную правленный
файл — текст в «Количество».
"""

from __future__ import annotations

import math

import pandas as pd

from app.helpers import (
    NO_BOX_LABEL,
    box_label_map,
    clean_id,
    clean_text,
    item_row_changed,
    qty_total,
    to_qty,
)


# --------------------------------------------------------------------------- #
# clean_text / clean_id (NaN-безопасные строки)
# --------------------------------------------------------------------------- #


def test_clean_text_handles_nan_and_none():
    assert clean_text(None) == ""
    assert clean_text(float("nan")) == ""
    assert clean_text(math.nan) == ""
    assert clean_text(pd.NA) == ""


def test_clean_text_trims_and_stringifies():
    assert clean_text("  Отвёртка  ") == "Отвёртка"
    assert clean_text(5) == "5"
    assert clean_text("") == ""


def test_clean_id_matches_clean_text():
    assert clean_id(float("nan")) == ""
    assert clean_id(" a1b2c3d4 ") == "a1b2c3d4"


# --------------------------------------------------------------------------- #
# to_qty (безопасное количество)
# --------------------------------------------------------------------------- #


def test_to_qty_coerces_garbage_to_zero():
    assert to_qty(float("nan")) == 0
    assert to_qty(None) == 0
    assert to_qty("текст") == 0
    assert to_qty("") == 0


def test_to_qty_keeps_numbers_and_clamps_negatives():
    assert to_qty(3) == 3
    assert to_qty(3.7) == 3
    assert to_qty("5") == 5
    assert to_qty(-2) == 0


# --------------------------------------------------------------------------- #
# qty_total (суммы по колонке «Количество»)
# --------------------------------------------------------------------------- #


def test_qty_total_on_empty_or_missing_column():
    assert qty_total(pd.DataFrame()) == 0
    assert qty_total(pd.DataFrame({"Название": ["x"]})) == 0


def test_qty_total_sums_numeric_and_ignores_text():
    items = pd.DataFrame({"Количество": [1, "2", "текст", None, 4]})
    assert qty_total(items) == 7


# --------------------------------------------------------------------------- #
# box_label_map (уникальные подписи при дублях имён ящиков)
# --------------------------------------------------------------------------- #


def _boxes_frame(rows: list[list]) -> pd.DataFrame:
    return pd.DataFrame(rows, columns=["ID", "Название", "Место_ID"])


def test_box_label_map_plain_names_without_duplicates():
    boxes = _boxes_frame([["b1", "Ящик А", ""], ["b2", "Ящик Б", "loc1"]])
    locations = pd.DataFrame([["loc1", "Гараж"]], columns=["ID", "Название"])

    labels = box_label_map(boxes, locations)
    assert labels == {"b1": "Ящик А", "b2": "Ящик Б · Гараж"}


def test_box_label_map_duplicates_get_id_suffix():
    boxes = _boxes_frame([["abcdef12", "Ящик", ""], ["12345678", "Ящик", ""]])
    labels = box_label_map(boxes, pd.DataFrame())

    # Ключи остаются ID, подписи различаются, вещь не уедет в чужой ящик.
    assert set(labels) == {"abcdef12", "12345678"}
    assert len(set(labels.values())) == 2
    assert labels["abcdef12"] == "Ящик · #ef12"
    assert labels["12345678"] == "Ящик · #5678"


def test_box_label_map_labels_never_equal_no_box_sentinel():
    boxes = _boxes_frame([["box00001", NO_BOX_LABEL, ""]])
    labels = box_label_map(boxes, pd.DataFrame())

    assert labels["box00001"] != NO_BOX_LABEL


# --------------------------------------------------------------------------- #
# item_row_changed (сравнение до простановки «Обновлён»)
# --------------------------------------------------------------------------- #


def _original(**overrides) -> pd.Series:
    row = {
        "ID": "itm1",
        "Название": "Отвёртка",
        "Ящик_ID": "b1",
        "Количество": 3,
        "Категория": "Инструменты",
        "Заметки": "крестовая",
        "Обновлён": "2026-01-01 10:00:00",
    }
    row.update(overrides)
    return pd.Series(row)


def test_item_row_changed_false_for_identical_row():
    values = {
        "Название": "Отвёртка",
        "Ящик_ID": "b1",
        "Количество": 3,
        "Категория": "Инструменты",
        "Заметки": "крестовая",
    }
    assert item_row_changed(_original(), values) is False


def test_item_row_changed_false_for_whitespace_only_edits():
    values = {
        "Название": "  Отвёртка  ",
        "Ящик_ID": "b1",
        "Количество": "3",
        "Категория": " инструменты ",  # регистровый вариант того же канона
        "Заметки": " крестовая ",
    }
    assert item_row_changed(_original(), values, ["Инструменты"]) is False


def test_item_row_changed_true_for_real_changes():
    values = {
        "Название": "Отвёртка",
        "Ящик_ID": "b1",
        "Количество": 4,
        "Категория": "Инструменты",
        "Заметки": "крестовая",
    }
    assert item_row_changed(_original(), values) is True
    assert item_row_changed(_original(Заметки="плоская"), values) is True
