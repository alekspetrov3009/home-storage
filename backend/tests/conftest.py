"""Общие фикстуры и генераторы xlsx-фикстур для тестов.

Фикстуры создаются программно через openpyxl — реальные пользовательские
данные в репозиторий не попадают никогда.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import app.context as context
from app.config import get_config
from openpyxl import Workbook

SHEET_LOCATIONS = "Места"
SHEET_BOXES = "Ящики"
SHEET_ITEMS = "Вещи"

LOCATION_HEADERS = ["ID", "Название", "Описание", "Создан"]
BOX_HEADERS = ["ID", "Название", "Место_ID", "Описание", "Создан"]
ITEM_HEADERS = [
    "ID", "Название", "Ящик_ID", "Количество", "Категория", "Заметки", "Обновлён",
]

# Шапка листа "Ящики" в старом формате (до появления мест хранения).
LEGACY_BOX_HEADERS = ["ID", "Название", "Место", "Описание", "Создан"]


def make_new_workbook(
    path: Path,
    locations: list[list] | None = None,
    boxes: list[list] | None = None,
    items: list[list] | None = None,
) -> Path:
    """Создаёт файл данных в новом (актуальном) формате."""
    wb = Workbook()
    ws = wb.active
    ws.title = SHEET_LOCATIONS
    ws.append(LOCATION_HEADERS)
    for row in locations or []:
        ws.append(row)

    boxes_ws = wb.create_sheet(SHEET_BOXES)
    boxes_ws.append(BOX_HEADERS)
    for row in boxes or []:
        boxes_ws.append(row)

    items_ws = wb.create_sheet(SHEET_ITEMS)
    items_ws.append(ITEM_HEADERS)
    for row in items or []:
        items_ws.append(row)

    wb.save(path)
    return path


def make_legacy_workbook(
    path: Path,
    legacy_boxes: list[list],
    extra_locations: list[list] | None = None,
    items: list[list] | None = None,
) -> Path:
    """Создаёт файл данных в СТАРОМ формате: у ящиков текстовая колонка «Место».

    Лист «Места» может как существовать (extra_locations), так и отсутствовать.
    """
    wb = Workbook()
    if extra_locations is not None:
        ws = wb.active
        ws.title = SHEET_LOCATIONS
        ws.append(LOCATION_HEADERS)
        for row in extra_locations:
            ws.append(row)
        boxes_ws = wb.create_sheet(SHEET_BOXES)
    else:
        # Старый файл мог не иметь листа «Места» вовсе; ящики — первый лист.
        boxes_ws = wb.active
        boxes_ws.title = SHEET_BOXES

    boxes_ws.append(LEGACY_BOX_HEADERS)
    for row in legacy_boxes:
        boxes_ws.append(row)

    items_ws = wb.create_sheet(SHEET_ITEMS)
    items_ws.append(ITEM_HEADERS)
    for row in items or []:
        items_ws.append(row)

    wb.save(path)
    return path


def read_sheet(path: Path, title: str) -> list[list]:
    """Читает лист файла как список строк (values_only)."""
    from openpyxl import load_workbook

    wb = load_workbook(path)
    return [list(row) for row in wb[title].iter_rows(values_only=True)]


@pytest.fixture
def data_file(tmp_path: Path) -> Path:
    """Путь к файлу-хранилищу во временном каталоге."""
    return tmp_path / "inventory.xlsx"


@pytest.fixture
def client(monkeypatch, data_file: Path) -> TestClient:
    """TestClient поверх приложения, нацеленного на tmp-фикстуру данных.

    Перед прогоном сбрасываются конфиг-кэш и синглтон сервиса, чтобы API
    прочитал tmp-фикстуру, а не данные соседних тестов.
    """
    from app.api.main import app

    monkeypatch.setenv("DATA_FILE", str(data_file))
    get_config.cache_clear()
    context._service = None
    yield TestClient(app)
    # Чужие тесты не должны увидеть наш синглтон и закэшированный конфиг.
    context._service = None
    get_config.cache_clear()
