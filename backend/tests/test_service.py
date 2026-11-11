"""Тесты сервисного слоя: сценарии, ссылочная целостность, поиск, кэш."""

from __future__ import annotations

import pandas as pd
import pytest
from datetime import datetime

from app.domain.errors import NotFoundError, StorageError, ValidationError
from app.domain.fields import ITEM_FIELDS
from app.domain.trash import DeletedEntry
from app.services.caching import CachedRepository
from app.services.inventory_service import InventoryService
from app.storage.excel_repository import ExcelRepository


@pytest.fixture
def service(data_file) -> InventoryService:
    return InventoryService(ExcelRepository(str(data_file)))


def test_runtime_checkable_protocol_accepts_repository(data_file):
    from app.services.repository import InventoryRepository

    assert isinstance(ExcelRepository(str(data_file)), InventoryRepository)
    assert isinstance(CachedRepository(ExcelRepository(str(data_file))), InventoryRepository)


# --------------------------------------------------------------------------- #
# Сценарии создания
# --------------------------------------------------------------------------- #


def test_create_location_validates_name(service):
    with pytest.raises(ValidationError, match="Укажите название места хранения"):
        service.create_location("   ", "")


def test_create_box_validates_name(service):
    with pytest.raises(ValidationError, match="Укажите название ящика"):
        service.create_box("", "", "")


def test_create_item_validates_name_and_quantity(service):
    box_id = service.create_box("Ящик", "", "")
    with pytest.raises(ValidationError, match="Укажите название вещи"):
        service.create_item("", box_id, 1, "", "")
    with pytest.raises(ValidationError, match="отрицательным"):
        service.create_item("Отвёртка", box_id, -1, "", "")
    with pytest.raises(ValidationError, match="целым числом"):
        service.create_item("Отвёртка", box_id, 1.5, "", "")


def test_create_box_with_unknown_location_fails(service):
    with pytest.raises(StorageError, match="не найдено"):
        service.create_box("Ящик", "nope", "")


# --------------------------------------------------------------------------- #
# Перенос и удаление
# --------------------------------------------------------------------------- #


def test_move_item_to_existing_box(service):
    box1 = service.create_box("Ящик 1", "", "")
    box2 = service.create_box("Ящик 2", "", "")
    item_id = service.create_item("Отвёртка", box1, 3, "", "")

    service.move_item(item_id, box2)
    row = service.load_items().iloc[0]
    assert row["Ящик_ID"] == box2


def test_move_item_to_unknown_box_fails(service):
    box1 = service.create_box("Ящик 1", "", "")
    item_id = service.create_item("Отвёртка", box1, 3, "", "")
    with pytest.raises(NotFoundError, match="Ящик с ID nope не найден"):
        service.move_item(item_id, "nope")
    # Вещь осталась на месте.
    assert service.load_items().iloc[0]["Ящик_ID"] == box1


def test_update_item_validates_quantity(service):
    box_id = service.create_box("Ящик", "", "")
    item_id = service.create_item("Отвёртка", box_id, 3, "", "")
    with pytest.raises(ValidationError, match="целым числом"):
        service.update_item(item_id, {"Количество": "много"})
    with pytest.raises(ValidationError, match="отрицательным"):
        service.update_item(item_id, {"Количество": -2})
    # Ноль допустим.
    service.update_item(item_id, {"Количество": 0})
    assert service.load_items().iloc[0]["Количество"] == 0


def test_delete_box_with_items_moves_box_to_trash_and_detaches(service):
    box_id = service.create_box("Ящик", "", "")
    item_id = service.create_item("Отвёртка", box_id, 1, "", "")
    entry = service.delete_box(box_id)
    assert entry.kind == "ящик" and entry.id == box_id
    items = service.load_items()
    assert items.iloc[0]["ID"] == item_id          # вещь цела
    assert items.iloc[0]["Ящик_ID"] == box_id      # detached: ссылка сохранена
    assert service.load_boxes().empty


def test_delete_location_with_boxes_detaches_boxes(service):
    loc_id = service.create_location("Гараж", "")
    box_id = service.create_box("Ящик", loc_id, "")
    service.delete_location(loc_id)
    boxes = service.load_boxes()
    assert boxes.iloc[0]["ID"] == box_id
    assert boxes.iloc[0]["Место_ID"] == loc_id  # ящик остался, без места


# --------------------------------------------------------------------------- #
# Поиск
# --------------------------------------------------------------------------- #


def test_search_item_ids_matches_name_category_notes_and_box(service):
    box1 = service.create_box("Ящик №1", "", "")
    service.create_item("Отвёртка", box1, 1, "Инструменты", "крестовая")
    service.create_item("Гвозди", box1, 100, "Расходники", "")
    service.create_item("Ёлочная гирлянда", box1, 2, "Декор", "новогодняя")

    boxes = service.load_boxes()
    labels = {str(boxes.iloc[0]["ID"]): "Ящик №1"}
    items = service.load_items()

    assert service.search_item_ids(items, labels, "отвёрт") == [
        str(items.iloc[0]["ID"])
    ]
    assert service.search_item_ids(items, labels, "инструменты") == [
        str(items.iloc[0]["ID"])
    ]
    # Поиск по названию ящика.
    assert len(service.search_item_ids(items, labels, "ящик №1")) == 3
    assert service.search_item_ids(items, labels, "несуществующее") == []


def test_search_on_empty_table_does_not_crash(service):
    assert service.search_item_ids(service.load_items(), {}, "что-угодно") == []


# --------------------------------------------------------------------------- #
# Общий список категорий
# --------------------------------------------------------------------------- #


def test_get_categories_empty_table(service):
    assert service.get_categories() == []


def test_get_categories_shared_across_items_sorted_and_deduped(service):
    box_id = service.create_box("Ящик", "", "")
    service.create_item("Отвёртка", box_id, 1, "Инструменты", "")
    service.create_item("Гвозди", box_id, 1, "расходники", "")
    service.create_item("Молоток", box_id, 1, "Инструменты", "")  # дубликат
    service.create_item("Пила", box_id, 1, "  ", "")               # пустая — не считается

    categories = service.get_categories()
    assert categories == ["Инструменты", "расходники"]  # сортировка и без дубликатов


def test_get_categories_dedupes_case_insensitively(service):
    """«Инструменты» и «инструменты» — одна категория; канон — первое написание."""
    box_id = service.create_box("Ящик", "", "")
    service.create_item("Отвёртка", box_id, 1, "Инструменты", "")
    service.create_item("Гвозди", box_id, 1, "инструменты", "")
    service.create_item("Пила", box_id, 1, "ИНСТРУМЕНТЫ", "")

    assert service.get_categories() == ["Инструменты"]


def test_category_survives_while_used_by_any_item(service):
    # Категория общая: видна, пока её использует хотя бы одна вещь.
    box_id = service.create_box("Ящик", "", "")
    i1 = service.create_item("Отвёртка", box_id, 1, "Инструменты", "")
    service.create_item("Молоток", box_id, 1, "Инструменты", "")
    service.delete_item(i1)
    assert service.get_categories() == ["Инструменты"]


# --------------------------------------------------------------------------- #
# Кэширующая обёртка
# --------------------------------------------------------------------------- #


def test_cached_repository_delegates_writes_and_all_reads(data_file):
    recorded: list[tuple] = []

    class RecordingRepo:
        def load_boxes(self):
            recorded.append(("load_boxes",))
            return pd.DataFrame({"ID": pd.Series(dtype="object")})

        def load_items(self):
            recorded.append(("load_items",))
            return pd.DataFrame({"ID": pd.Series(dtype="object")})

        def load_locations(self):
            recorded.append(("load_locations",))
            return pd.DataFrame({"ID": pd.Series(dtype="object")})

        def add_location(self, name, description):
            recorded.append(("add_location", name))
            return "loc1"

        def delete_location(self, location_id):
            recorded.append(("delete_location", location_id))
            return DeletedEntry("место", location_id, "Гараж", "", "", {})

        def add_box(self, name, location_id, description, color=""):
            recorded.append(("add_box", name))
            return "box1"

        def delete_box(self, box_id):
            recorded.append(("delete_box", box_id))
            return DeletedEntry("ящик", box_id, "Ящик", "", "", {})

        def add_item(self, name, box_id, qty, category, notes):
            recorded.append(("add_item", name))
            return "itm1"

        def update_item(self, item_id, fields):
            recorded.append(("update_item", item_id, fields))

        def delete_item(self, item_id):
            recorded.append(("delete_item", item_id))
            return DeletedEntry("вещь", item_id, "Отвёртка", "", "", {})

        def delete_items(self, item_ids):
            recorded.append(("delete_items", list(item_ids)))
            return []

        def replace_items(self, df):
            recorded.append(("replace_items", len(df)))

        def load_trash(self):
            recorded.append(("load_trash",))
            return pd.DataFrame({"ID": pd.Series(dtype="object")})

        def trash_restore(self, kind, entity_id):
            recorded.append(("trash_restore", kind, entity_id))
            return "Отвёртка"

        def trash_clear(self):
            recorded.append(("trash_clear",))
            return 0

        def trash_purge_expired(self, now, days):
            recorded.append(("trash_purge_expired", now, days))
            return 0

        def backup_file(self):
            recorded.append(("backup_file",))
            return "backup.xlsx"

    wrapper = CachedRepository(RecordingRepo())

    # Все чтения доходят до репозитория.
    wrapper.load_boxes(); wrapper.load_items(); wrapper.load_locations(); wrapper.load_trash()
    assert [r[0] for r in recorded] == ["load_boxes", "load_items", "load_locations", "load_trash"]

    # Все записи доходят до репозитория без кэширования.
    assert wrapper.add_location("Гараж", "") == "loc1"
    wrapper.delete_location("loc1")
    assert wrapper.add_box("Ящик", "", "") == "box1"
    wrapper.delete_box("box1")
    assert wrapper.add_item("Отвёртка", "box1", 1, "", "") == "itm1"
    wrapper.update_item("itm1", {"Количество": 5})
    wrapper.delete_item("itm1")
    wrapper.delete_items(["itm2"])
    wrapper.replace_items(pd.DataFrame({"ID": ["a"]}))
    assert wrapper.trash_restore("вещь", "x") == "Отвёртка"
    wrapper.trash_clear()
    wrapper.trash_purge_expired(datetime.now(), 30)
    assert wrapper.backup_file() == "backup.xlsx"

    names = [r[0] for r in recorded][4:]
    assert names == [
        "add_location", "delete_location", "add_box", "delete_box",
        "add_item", "update_item", "delete_item", "delete_items",
        "replace_items", "trash_restore", "trash_clear",
        "trash_purge_expired", "backup_file",
    ]


def test_service_delete_item_delegates(service):
    box_id = service.create_box("Ящик", "", "")
    item_id = service.create_item("Отвёртка", box_id, 1, "", "")
    service.delete_item(item_id)
    assert service.load_items().empty


def test_service_load_locations_delegates(service):
    service.create_location("Гараж", "")
    locations = service.load_locations()
    assert locations.iloc[0]["Название"] == "Гараж"


def test_cached_repository_reads_once_until_cache_cleared(data_file):
    calls = {"n": 0}

    class CountingRepo:
        def load_boxes(self):
            calls["n"] += 1
            return pd.DataFrame({"ID": pd.Series(dtype="object")})

        def load_items(self):
            return pd.DataFrame({"ID": pd.Series(dtype="object")})

        def load_locations(self):
            return pd.DataFrame({"ID": pd.Series(dtype="object")})

        def load_trash(self):
            return pd.DataFrame({"ID": pd.Series(dtype="object")})

        def add_box(self, *a, **kw):
            return "box1"

    cached = CachedRepository(CountingRepo())
    cached.load_boxes()
    cached.load_boxes()
    cached.load_boxes()
    assert calls["n"] == 1  # чтения кэшируются

    cached.clear_cache()
    cached.load_boxes()
    assert calls["n"] == 2  # сброс кэша заставил перечитать

    # Запись не кэшируется и не сбрасывает кэш сама.
    cached.add_box("Ящик", "", "")
    assert calls["n"] == 2


def test_service_clear_cache_delegates_to_wrapper(data_file):
    class FlaggedRepo:
        def __init__(self):
            self.cleared = False

        def clear_cache(self):
            self.cleared = True

    service = InventoryService(FlaggedRepo())
    service.clear_cache()
    assert service._repo.cleared is True


def test_service_clear_cache_without_cache_support(data_file):
    # Репозиторий без clear_cache (например, голый ExcelRepository) —
    # clear_cache просто ничего не делает.
    service = InventoryService(ExcelRepository(str(data_file)))
    service.clear_cache()  # не падает


def test_service_backup_and_replace_delegate(service, data_file):
    box_id = service.create_box("Ящик", "", "")
    service.create_item("Отвёртка", box_id, 2, "", "")

    # replace_items делегируется в репозиторий.
    df = pd.DataFrame(
        [["new1", "Новая", box_id, 1, "", "", ""]], columns=ITEM_FIELDS
    )
    service.replace_items(df)
    assert service.load_items().iloc[0]["ID"] == "new1"

    backup = service.backup_file()
    assert backup.endswith(".backup.xlsx")


def test_service_update_item_allows_name_and_text_fields(service):
    box_id = service.create_box("Ящик", "", "")
    item_id = service.create_item("Отвёртка", box_id, 2, "Инстр", "")
    service.update_item(item_id, {"Название": "Отвёртка большая", "Категория": "Инструменты"})
    row = service.load_items().iloc[0]
    assert row["Название"] == "Отвёртка большая"

    with pytest.raises(ValidationError, match="Укажите название вещи"):
        service.update_item(item_id, {"Название": "   "})
