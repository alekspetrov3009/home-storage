"""Тесты модуля миграции legacy-формата (изолированно, на уровне книги)."""

from __future__ import annotations

import pytest
from openpyxl import Workbook, load_workbook

from app.storage.migration import migrate_legacy_boxes
from app.storage.schema import BOX_HEADERS, LEGACY_BOX_HEADERS, LOCATION_HEADERS

from conftest import read_sheet


def _legacy_book(boxes: list[list], with_locations: bool = False) -> Workbook:
    wb = Workbook()
    if with_locations:
        ws = wb.active
        ws.title = "Места"
        ws.append(LOCATION_HEADERS)
    else:
        ws = wb.active
        ws.title = "Ящики"
    boxes_ws = ws if not with_locations else wb.create_sheet("Ящики")
    boxes_ws.append(LEGACY_BOX_HEADERS)
    for row in boxes:
        boxes_ws.append(row)
    return wb


def test_migrate_merges_duplicate_places_case_insensitive(tmp_path):
    wb = _legacy_book(
        [
            ["box1", "Ящик А", "Гараж", "первый", "2024-01-01 10:00:00"],
            ["box2", "Ящик Б", "гараж", "второй", "2024-01-01 10:01:00"],
            ["box3", "Ящик В", "Балкон", "", "2024-01-01 10:02:00"],
            ["box4", "Ящик Г", "", "без места", "2024-01-01 10:03:00"],
        ]
    )
    assert migrate_legacy_boxes(wb) is True

    # Сохраняем и проверяем результат на диске.
    path = tmp_path / "inventory.xlsx"
    wb.save(path)

    rows = read_sheet(path, "Ящики")
    assert rows[0] == BOX_HEADERS
    boxes = {r[0]: r for r in rows[1:]}
    assert boxes["box1"][2] == boxes["box2"][2]  # «Гараж» и «гараж» — одно место
    assert boxes["box3"][2] != boxes["box1"][2]
    # openpyxl сохраняет пустую строку как None — на диске это одно и то же.
    assert not boxes["box4"][2]  # пустое место — ящик без места

    locations = [r for r in read_sheet(path, "Места")[1:]]
    assert sorted(r[1] for r in locations) == ["Балкон", "Гараж"]


def test_migrate_creates_missing_locations_sheet(tmp_path):
    wb = _legacy_book([["box1", "Ящик А", "Кладовка", "", "2024-01-01 10:00:00"]])
    assert migrate_legacy_boxes(wb) is True

    path = tmp_path / "inventory.xlsx"
    wb.save(path)
    locations = read_sheet(path, "Места")
    assert locations[0] == LOCATION_HEADERS
    assert locations[1][1] == "Кладовка"
    assert read_sheet(path, "Ящики")[1][2] == locations[1][0]


def test_migrate_reuses_existing_locations(tmp_path):
    wb = _legacy_book(
        [["box1", "Ящик А", "Гараж", "", "2024-01-01 10:00:00"]],
        with_locations=True,
    )
    # «Гараж» уже есть на листе «Места» — дубликат не создаётся.
    wb["Места"].append(["loc42", "Гараж", "", "2024-01-01 09:00:00"])
    assert migrate_legacy_boxes(wb) is True

    path = tmp_path / "inventory.xlsx"
    wb.save(path)
    locations = read_sheet(path, "Места")[1:]
    assert len(locations) == 1
    assert locations[0][0] == "loc42"
    assert read_sheet(path, "Ящики")[1][2] == "loc42"


def test_new_format_is_not_migrated():
    wb = Workbook()
    ws = wb.active
    ws.title = "Ящики"
    ws.append(BOX_HEADERS)
    ws.append(["box1", "Ящик А", "loc1", "", "2024-01-01 10:00:00"])
    assert migrate_legacy_boxes(wb) is False


def test_unknown_format_is_not_migrated():
    wb = Workbook()
    ws = wb.active
    ws.title = "Ящики"
    ws.append(["ID", "Название", "Что-то другое", "Описание", "Создан"])
    ws.append(["box1", "Ящик А", "значение", "", "2024-01-01 10:00:00"])
    assert migrate_legacy_boxes(wb) is False


def test_missing_boxes_sheet_is_not_migrated():
    wb = Workbook()
    wb.active.title = "Вещи"
    assert migrate_legacy_boxes(wb) is False


def test_empty_legacy_sheet_is_rewritten_to_new_format():
    wb = _legacy_book([])
    # Даже без строк шапка меняется на новую — это тоже миграция формата.
    assert migrate_legacy_boxes(wb) is True
    assert [c.value for c in wb["Ящики"][1]] == BOX_HEADERS


def test_blank_and_idless_rows_are_skipped(tmp_path):
    wb = _legacy_book(
        [
            [None, None, None, None, None],
            ["", "", "", "", ""],
            [None, "Ящик без ID", "Гараж", "", ""],
            ["box1", "Ящик А", "Гараж", "", "2024-01-01 10:00:00"],
        ]
    )
    assert migrate_legacy_boxes(wb) is True

    path = tmp_path / "inventory.xlsx"
    wb.save(path)
    rows = [r for r in read_sheet(path, "Ящики")[1:] if r and r[0]]
    assert len(rows) == 1
    assert rows[0][0] == "box1"
    # Место создано только для строки с ID.
    assert len(read_sheet(path, "Места")[1:]) == 1
