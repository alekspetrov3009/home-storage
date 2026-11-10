"""Тесты корзины: удаление с восстановлением, каскады, срок хранения.

Слои: домен (expiry), репозиторий (лист «Корзина»), сервис (политики
удаления и восстановления).
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from app.domain.errors import StorageError
from app.domain.trash import (
    TRASH_KIND_BOX,
    TRASH_KIND_ITEM,
    TRASH_KIND_LOCATION,
    DeletedEntry,
    is_expired,
    parse_ts,
)
from app.services.inventory_service import InventoryService
from app.storage.excel_repository import ExcelRepository

from conftest import read_sheet

SHEET_TRASH = "Корзина"
TRASH_HEADERS = ["Тип", "ID", "Название", "Данные", "Родитель_ID", "Дата удаления"]


@pytest.fixture
def service(data_file) -> InventoryService:
    return InventoryService(ExcelRepository(str(data_file)))


@pytest.fixture
def repo(data_file) -> ExcelRepository:
    return ExcelRepository(str(data_file))


# --------------------------------------------------------------------------- #
# Домен: расчёт истечения срока
# --------------------------------------------------------------------------- #


def test_parse_ts_roundtrip_and_garbage():
    assert parse_ts("2024-01-02 03:04:05") == datetime(2024, 1, 2, 3, 4, 5)
    assert parse_ts("") is None
    assert parse_ts("мусор") is None
    assert parse_ts(None) is None


def test_is_expired_respects_30_days():
    now = datetime(2024, 6, 1, 12, 0, 0)
    fresh = now - timedelta(days=29)
    old = now - timedelta(days=31)
    assert not is_expired(fresh, now)
    assert is_expired(old, now)
    # Ровно 30 дней назад — ещё не истекла (истекает строго позже срока).
    assert not is_expired(now - timedelta(days=30), now)


def test_is_expired_unparseable_date_is_kept():
    # Неразбираемая отметка не считается истекшей: запись не вычищается молча.
    assert not is_expired("мусор", datetime.now())


# --------------------------------------------------------------------------- #
# Репозиторий: лист «Корзина»
# --------------------------------------------------------------------------- #


def test_trash_sheet_is_created_lazily(repo, data_file):
    repo.load_boxes()  # файл создан, но корзины ещё нет
    assert SHEET_TRASH not in read_sheet_names(data_file)

    # Первое удаление создаёт лист с нужной шапкой.
    box_id = repo.add_box("Ящик", "", "")
    repo.delete_box(box_id)
    rows = read_sheet(data_file, SHEET_TRASH)
    assert rows[0] == TRASH_HEADERS
    assert rows[1][0] == TRASH_KIND_BOX


def read_sheet_names(path) -> list[str]:
    from openpyxl import load_workbook

    return load_workbook(path).sheetnames


def test_load_trash_without_sheet_returns_empty_frame(repo, data_file):
    make_minimal_file(data_file)
    trash = repo.load_trash()
    assert trash.empty
    assert list(trash.columns) == TRASH_HEADERS
    # Чтение НЕ создаёт лист.
    assert SHEET_TRASH not in read_sheet_names(data_file)


def test_trash_roundtrip_integrity(repo, data_file):
    """Исходные значения строки переживают удаление и восстановление."""
    loc_id = repo.add_location("Гараж", "описание места")
    box_id = repo.add_box("Ящик №1", loc_id, "инструменты")
    item_id = repo.add_item("Отвёртка", box_id, 3, "Инструменты", "крестовая")

    repo.delete_item(item_id)
    trash = repo.load_trash()
    assert len(trash) == 1
    row = trash.iloc[0]
    assert row["Тип"] == TRASH_KIND_ITEM
    assert row["ID"] == item_id
    assert row["Название"] == "Отвёртка"
    assert row["Родитель_ID"] == box_id
    assert str(row["Дата удаления"]).strip()

    name = repo.trash_restore(TRASH_KIND_ITEM, item_id)
    assert name == "Отвёртка"
    items = repo.load_items()
    assert items.iloc[0]["ID"] == item_id
    assert items.iloc[0]["Название"] == "Отвёртка"
    assert items.iloc[0]["Ящик_ID"] == box_id
    assert int(items.iloc[0]["Количество"]) == 3
    assert items.iloc[0]["Категория"] == "Инструменты"
    assert items.iloc[0]["Заметки"] == "крестовая"
    assert repo.load_trash().empty


def make_minimal_file(data_file) -> None:
    from openpyxl import Workbook

    from app.domain.fields import BOX_FIELDS, ITEM_FIELDS, LOCATION_FIELDS

    wb = Workbook()
    ws = wb.active
    ws.title = "Места"
    ws.append(LOCATION_FIELDS)
    wb.create_sheet("Ящики").append(BOX_FIELDS)
    wb.create_sheet("Вещи").append(ITEM_FIELDS)
    wb.save(data_file)


# --------------------------------------------------------------------------- #
# Сервис: удаление и восстановление
# --------------------------------------------------------------------------- #


def test_delete_item_goes_to_trash_and_restores_with_same_id(service):
    box_id = service.create_box("Ящик", "", "")
    item_id = service.create_item("Отвёртка", box_id, 2, "Инструменты", "")

    entry = service.delete_item(item_id)
    assert entry.kind == TRASH_KIND_ITEM
    assert entry.id == item_id
    assert entry.name == "Отвёртка"
    assert entry.parent_id == box_id

    items = service.load_items()
    assert items.empty  # из «Вещей» исчезла

    entries = service.trash_entries()
    assert [e.id for e in entries] == [item_id]

    assert service.restore(TRASH_KIND_ITEM, item_id) == "Отвёртка"
    restored = service.load_items().iloc[0]
    assert restored["ID"] == item_id  # ID не меняется
    assert restored["Ящик_ID"] == box_id


def test_restore_item_when_box_is_gone_detaches(service):
    box_id = service.create_box("Ящик", "", "")
    item_id = service.create_item("Отвёртка", box_id, 1, "", "")
    service.delete_item(item_id)
    service.delete_box(box_id)

    # Убираем из корзины только запись ящика: вещь остаётся, а её ящик
    # исчез навсегда — восстановленная вещь должна оказаться «без ящика».
    from openpyxl import load_workbook

    wb = load_workbook(service._repo._data_file)
    ws = wb["Корзина"]
    for row_idx in range(ws.max_row, 1, -1):
        if str(ws.cell(row=row_idx, column=1).value) == TRASH_KIND_BOX:
            ws.delete_rows(row_idx)
    wb.save(service._repo._data_file)

    service.restore(TRASH_KIND_ITEM, item_id)
    restored = service.load_items().iloc[0]
    # Ящика больше нет — вещь восстановлена «без ящика» (ссылка сохранена).
    assert restored["ID"] == item_id
    assert service.load_boxes().empty


def test_delete_box_with_items_detaches_restore_reattaches(service):
    box_id = service.create_box("Ящик", "", "")
    i1 = service.create_item("Отвёртка", box_id, 1, "", "")
    i2 = service.create_item("Молоток", box_id, 2, "", "")

    service.delete_box(box_id)

    # Вещи целы и отсоединены (Ящик_ID указывает на удалённый ящик).
    items = service.load_items()
    assert sorted(items["ID"].astype(str)) == sorted([i1, i2])
    assert (items["Ящик_ID"].astype(str) == box_id).all()

    # Восстановление ящика автоматически возвращает вещи (ID не менялись).
    service.restore(TRASH_KIND_BOX, box_id)
    boxes = service.load_boxes()
    assert boxes.iloc[0]["ID"] == box_id
    assert service.load_items().iloc[0]["Ящик_ID"] == box_id


def test_delete_location_with_boxes_detaches_restore_reattaches(service):
    loc_id = service.create_location("Гараж", "")
    box_id = service.create_box("Ящик", loc_id, "")

    service.delete_location(loc_id)
    boxes = service.load_boxes()
    assert boxes.iloc[0]["ID"] == box_id          # ящик цел
    assert boxes.iloc[0]["Место_ID"] == loc_id    # отсоединён

    service.restore(TRASH_KIND_LOCATION, loc_id)
    boxes = service.load_boxes()
    assert boxes.iloc[0]["Место_ID"] == loc_id    # привязка ожила


def test_purge_respects_30_day_expiry(service):
    box_id = service.create_box("Ящик", "", "")
    item_id = service.create_item("Отвёртка", box_id, 1, "", "")
    service.delete_item(item_id)
    service.create_item("Свежая", box_id, 1, "", "")
    fresh_id = str(service.load_items().iloc[0]["ID"])
    service.delete_item(fresh_id)

    # Отметку «Дата удаления» первой записи меняем на 31 день назад —
    # напрямую в файле, как если бы запись пролежала в корзине месяц.
    from openpyxl import load_workbook

    wb = load_workbook(service._repo._data_file)
    ws = wb["Корзина"]
    ws.cell(row=2, column=6, value=(datetime.now() - timedelta(days=31)).strftime("%Y-%m-%d %H:%M:%S"))
    wb.save(service._repo._data_file)

    purged = service.purge_expired_trash()
    assert purged == 1
    remaining = service.load_trash()
    assert remaining["ID"].astype(str).tolist() == [fresh_id]


def test_purge_expired_trash_on_empty_trash(service):
    assert service.purge_expired_trash() == 0


def test_restore_from_empty_trash_gives_clear_error(service):
    with pytest.raises(StorageError, match="не найдена в корзине"):
        service.restore(TRASH_KIND_ITEM, "nope")


def test_restore_twice_gives_clear_error(service):
    box_id = service.create_box("Ящик", "", "")
    item_id = service.create_item("Отвёртка", box_id, 1, "", "")
    service.delete_item(item_id)
    service.restore(TRASH_KIND_ITEM, item_id)
    with pytest.raises(StorageError, match="не найдена в корзине"):
        service.restore(TRASH_KIND_ITEM, item_id)


def test_clear_trash(service):
    box_id = service.create_box("Ящик", "", "")
    service.create_item("Отвёртка", box_id, 1, "", "")
    service.delete_item(str(service.load_items().iloc[0]["ID"]))
    assert service.clear_trash() == 1
    assert service.load_trash().empty
    assert service.clear_trash() == 0  # повторно — уже пусто


def test_delete_missing_entity_errors(service):
    with pytest.raises(StorageError, match="не найдена"):
        service.delete_item("nope")
    with pytest.raises(StorageError, match="не найден"):
        service.delete_box("nope")
    with pytest.raises(StorageError, match="не найдено"):
        service.delete_location("nope")


# --------------------------------------------------------------------------- #
# Round-trip: корзина переживает сохранение и переоткрытие файла
# --------------------------------------------------------------------------- #


def test_trash_survives_save_load_roundtrip(data_file):
    first = InventoryService(ExcelRepository(str(data_file)))
    box_id = first.create_box("Ящик", "", "")
    item_id = first.create_item("Отвёртка", box_id, 3, "Кат", "заметка")
    first.delete_item(item_id)

    second = InventoryService(ExcelRepository(str(data_file)))
    entries = second.trash_entries()
    assert [e.id for e in entries] == [item_id]
    assert entries[0].name == "Отвёртка"
    assert entries[0].data.get("Количество") in (3, "3")

    assert second.restore(TRASH_KIND_ITEM, item_id) == "Отвёртка"
    third = InventoryService(ExcelRepository(str(data_file)))
    restored = third.load_items().iloc[0]
    assert restored["ID"] == item_id
    assert int(restored["Количество"]) == 3


def test_deleted_entry_from_row_is_robust_to_garbage():
    entry = DeletedEntry.from_row(
        {"Тип": TRASH_KIND_ITEM, "ID": "x1", "Название": "Штука",
         "Данные": "{битый json", "Родитель_ID": "", "Дата удаления": ""}
    )
    assert entry.data == {}  # битый JSON не роняет чтение корзины
