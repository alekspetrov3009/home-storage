"""Тесты слоя хранения: round-trip, атомарность, ошибки, изоляция openpyxl."""

from __future__ import annotations

import pandas as pd
import pytest

from app.domain.errors import StorageError
from app.domain.fields import (
    BOX_FIELDS,
    ITEM_FIELDS,
    LOCATION_FIELDS,
)
from app.storage.excel_repository import ExcelRepository

from conftest import make_legacy_workbook, make_new_workbook, read_sheet


@pytest.fixture
def repo(data_file) -> ExcelRepository:
    return ExcelRepository(str(data_file))


# --------------------------------------------------------------------------- #
# Пустое хранилище и round-trip
# --------------------------------------------------------------------------- #


def test_missing_file_is_created_with_three_sheets(repo, data_file):
    boxes = repo.load_boxes()
    items = repo.load_items()
    locations = repo.load_locations()

    assert list(boxes.columns) == BOX_FIELDS
    assert list(items.columns) == ITEM_FIELDS
    assert list(locations.columns) == LOCATION_FIELDS
    assert boxes.empty and items.empty and locations.empty
    assert data_file.exists()
    assert read_sheet(data_file, "Места")[0] == LOCATION_FIELDS
    assert read_sheet(data_file, "Ящики")[0] == BOX_FIELDS
    assert read_sheet(data_file, "Вещи")[0] == ITEM_FIELDS


def test_save_load_roundtrip_identical_data(repo, data_file):
    loc_id = repo.add_location("Гараж", "полка 1")
    box_id = repo.add_box("Ящик №1", loc_id, "инструменты")
    item_id = repo.add_item("Отвёртка", box_id, 3, "Инструменты", "крестовая")

    # Новый экземпляр репозитория над тем же файлом: данные идентичны.
    fresh = ExcelRepository(str(data_file))
    boxes, items, locations = fresh.load_boxes(), fresh.load_items(), fresh.load_locations()

    assert boxes.to_dict("records") == [
        {
            "ID": box_id,
            "Название": "Ящик №1",
            "Место_ID": loc_id,
            "Описание": "инструменты",
            "Создан": boxes.iloc[0]["Создан"],
        }
    ]
    assert locations.iloc[0]["Название"] == "Гараж"
    assert items.iloc[0]["ID"] == item_id
    assert items.iloc[0]["Количество"] == 3


# --------------------------------------------------------------------------- #
# Миграция legacy-формата (читается transparently при load_*)
# --------------------------------------------------------------------------- #


def test_legacy_file_migrates_on_first_read(repo, data_file):
    make_legacy_workbook(
        data_file,
        legacy_boxes=[
            ["box1", "Ящик А", "Гараж", "первый", "2024-01-01 10:00:00"],
            ["box2", "Ящик Б", "гараж", "второй", "2024-01-01 10:01:00"],
            ["box3", "Ящик В", "Балкон", "", "2024-01-01 10:02:00"],
        ],
    )
    locations = repo.load_locations()
    boxes = repo.load_boxes()

    # Дубликаты «Гараж»/«гараж» склеились в одно место.
    assert sorted(locations["Название"].tolist()) == ["Балкон", "Гараж"]
    assert boxes.set_index("ID").loc["box1", "Место_ID"] == \
        boxes.set_index("ID").loc["box2", "Место_ID"]
    # Файл перезаписан в новом формате.
    assert read_sheet(data_file, "Ящики")[0] == BOX_FIELDS


def test_migration_merges_with_existing_locations(repo, data_file):
    make_legacy_workbook(
        data_file,
        legacy_boxes=[["box1", "Ящик А", "Гараж", "", "2024-01-01 10:00:00"]],
        extra_locations=[["loc0", "Кладовка", "", "2024-01-01 09:00:00"]],
    )
    locations = repo.load_locations()
    # Существующее место «Кладовка» сохранено, новое добавлено.
    assert sorted(locations["Название"].tolist()) == ["Гараж", "Кладовка"]


def test_unknown_box_format_is_left_untouched(repo, data_file):
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.title = "Ящики"
    ws.append(["ID", "Название", "Что-то другое", "Описание", "Создан"])
    ws.append(["box1", "Ящик А", "значение", "", "2024-01-01 10:00:00"])
    wb.create_sheet("Вещи").append(ITEM_FIELDS)
    wb.save(data_file)

    repo.load_boxes()

    rows = read_sheet(data_file, "Ящики")
    assert rows[0][:3] == ["ID", "Название", "Что-то другое"]  # формат не тронут
    assert rows[1][2] == "значение"


def test_new_format_file_is_not_rewritten(repo, data_file):
    path = make_new_workbook(
        data_file, boxes=[["box1", "Ящик А", "locX", "", "2024-01-01 10:00:00"]]
    )
    before = path.read_bytes()
    repo.load_boxes()
    assert path.read_bytes() == before


# --------------------------------------------------------------------------- #
# Ошибки ссылочной целостности и валидации
# --------------------------------------------------------------------------- #


def test_add_box_with_unknown_location_fails(repo):
    with pytest.raises(StorageError, match="Место хранения с ID nope не найдено"):
        repo.add_box("Ящик", "nope", "")


def test_duplicate_location_name_fails(repo):
    repo.add_location("Гараж", "")
    with pytest.raises(StorageError, match="уже существует"):
        repo.add_location("гараж", "")


def test_delete_location_with_boxes_detaches_boxes(repo):
    loc_id = repo.add_location("Гараж", "")
    box_id = repo.add_box("Ящик", loc_id, "")
    entry = repo.delete_location(loc_id)
    assert entry.kind == "место"
    assert repo.load_locations().empty
    # Ящик остался, но без места (Место_ID указывает на удалённое место).
    boxes = repo.load_boxes()
    assert boxes.iloc[0]["ID"] == box_id
    assert boxes.iloc[0]["Место_ID"] == loc_id
    # Место попало в корзину и восстановимо.
    assert repo.load_trash().iloc[0]["ID"] == loc_id


def test_delete_location_succeeds_when_no_boxes_linked(repo):
    loc_id = repo.add_location("Гараж", "")
    repo.delete_location(loc_id)
    assert repo.load_locations().empty


def test_delete_missing_location_fails(repo):
    with pytest.raises(StorageError, match="не найдено"):
        repo.delete_location("nope")


def test_delete_box_moves_to_trash_and_detaches_items(repo):
    box_id = repo.add_box("Ящик", "", "")
    item_id = repo.add_item("Отвёртка", box_id, 1, "", "")
    entry = repo.delete_box(box_id)
    assert entry.kind == "ящик"
    # Вещь осталась нетронутой, со старым Ящик_ID (detach, не удаление).
    items = repo.load_items()
    assert items.iloc[0]["ID"] == item_id
    assert items.iloc[0]["Ящик_ID"] == box_id
    assert repo.load_boxes().empty
    # Ящик в корзине с исходными значениями.
    trash = repo.load_trash()
    assert trash.iloc[0]["ID"] == box_id
    assert trash.iloc[0]["Название"] == "Ящик"


def test_update_item_errors(repo):
    box_id = repo.add_box("Ящик", "", "")
    item_id = repo.add_item("Отвёртка", box_id, 3, "", "")

    with pytest.raises(StorageError, match="Неизвестные поля"):
        repo.update_item(item_id, {"Бред": 1})
    with pytest.raises(StorageError, match="не найдена"):
        repo.update_item("missing", {"Количество": 1})


def test_delete_item_twice_fails(repo):
    box_id = repo.add_box("Ящик", "", "")
    item_id = repo.add_item("Отвёртка", box_id, 1, "", "")
    repo.delete_item(item_id)
    with pytest.raises(StorageError, match="уже удалена"):
        repo.delete_item(item_id)


def test_replace_items_rewrites_sheet(repo):
    box_id = repo.add_box("Ящик", "", "")
    repo.add_item("Старая вещь", box_id, 1, "", "")

    df = pd.DataFrame(
        [["new1", "Новая", box_id, 5, "Кат", "заметка", ""]],
        columns=ITEM_FIELDS,
    )
    repo.replace_items(df)

    items = repo.load_items()
    assert len(items) == 1
    assert items.iloc[0]["ID"] == "new1"
    assert items.iloc[0]["Количество"] == 5
    assert str(items.iloc[0]["Обновлён"]).strip() != ""


def test_delete_items_with_duplicate_ids_dedupes(repo):
    """Дубликат ID во входном списке не пишет запись в корзину дважды и
    не удаляет чужую (сдвинувшуюся) строку; отсутствующие ID пропускаются."""
    box_id = repo.add_box("Ящик", "", "")
    id1 = repo.add_item("Отвёртка", box_id, 1, "", "")
    id2 = repo.add_item("Молоток", box_id, 2, "", "")
    id3 = repo.add_item("Пила", box_id, 3, "", "")

    entries = repo.delete_items([id1, id1, "missing", id2])

    # Одна запись в корзине на каждый уникальный ID.
    assert [e.id for e in entries] == [id1, id2]
    trash = repo.load_trash()
    assert sorted(trash["ID"].astype(str)) == sorted([id1, id2])
    # Соседние строки целы: осталась только Пила.
    items = repo.load_items()
    assert items["ID"].astype(str).tolist() == [id3]
    assert int(items.iloc[0]["Количество"]) == 3


def test_trash_restore_corrupted_json_raises_and_keeps_target_sheet(repo):
    """Повреждённая JSON-запись корзины не восстанавливается как пустая строка."""
    from app.domain.trash import TRASH_KIND_ITEM
    from openpyxl import load_workbook

    box_id = repo.add_box("Ящик", "", "")
    item_id = repo.add_item("Отвёртка", box_id, 1, "", "")
    repo.delete_item(item_id)

    wb = load_workbook(repo._data_file)
    wb["Корзина"].cell(row=2, column=4, value="{битый json")
    wb.save(repo._data_file)

    with pytest.raises(StorageError, match="Запись корзины повреждена"):
        repo.trash_restore(TRASH_KIND_ITEM, item_id)
    # Целевой лист не изменился: пустая строка не добавилась.
    assert repo.load_items().empty

    # Валидный JSON без ID — та же ошибка.
    import json

    wb = load_workbook(repo._data_file)
    wb["Корзина"].cell(row=2, column=4, value=json.dumps({"Название": "Отвёртка"}, ensure_ascii=False))
    wb.save(repo._data_file)

    with pytest.raises(StorageError, match="Запись корзины повреждена"):
        repo.trash_restore(TRASH_KIND_ITEM, item_id)
    assert repo.load_items().empty


def test_backup_file_creates_copy(repo):
    repo.add_box("Ящик", "", "")
    backup = repo.backup_file()
    assert backup.endswith(".backup.xlsx")
    assert read_sheet(backup, "Ящики")[0] == BOX_FIELDS


def test_corrupted_file_raises_storage_error(repo, data_file):
    data_file.write_bytes(b"not an excel file at all")
    # Повреждённый zip не является ни InvalidFileException, ни OSError —
    # попадает в общий обработчик с сообщением «Не удалось открыть файл».
    with pytest.raises(StorageError, match="Не удалось открыть файл"):
        repo.load_boxes()


def test_non_excel_zip_raises_invalid_file_message(repo, data_file):
    # Валидный zip с расширением, которое openpyxl не считает Excel-книгой,
    # даёт InvalidFileException — отдельная ветка с сообщением
    # «повреждён или не является книгой Excel».
    import zipfile

    with zipfile.ZipFile(data_file.with_suffix(".zip"), "w") as zf:
        zf.writestr("note.txt", "not a workbook")
    data_file_wrong_ext = data_file.with_suffix(".zip")

    repo2 = ExcelRepository(str(data_file_wrong_ext))
    with pytest.raises(StorageError, match="повреждён или не является книгой Excel"):
        repo2.load_boxes()


def test_wrong_header_of_empty_sheet_is_fixed(repo, data_file):
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.title = "Ящики"
    ws.append(["Старая", "Шапка"])  # неверная шапка пустого листа
    wb.save(data_file)

    boxes = repo.load_boxes()
    assert list(boxes.columns) == BOX_FIELDS
    # Шапка исправлена и сохранена на диск.
    assert read_sheet(data_file, "Ящики")[0] == BOX_FIELDS


def test_missing_sheet_is_recreated(repo, data_file):
    make_new_workbook(data_file, boxes=[["box1", "Ящик", "", "", ""]])
    from openpyxl import load_workbook

    wb = load_workbook(data_file)
    del wb["Вещи"]
    wb.save(data_file)

    items = repo.load_items()
    assert list(items.columns) == ITEM_FIELDS
    assert read_sheet(data_file, "Вещи")[0] == ITEM_FIELDS


# --------------------------------------------------------------------------- #
# Сбои ввода-вывода (monkeypatch os-функций)
# --------------------------------------------------------------------------- #


def test_save_failure_raises_storage_error(repo, monkeypatch):
    import app.storage.excel_repository as mod

    def broken_replace(src, dst):
        raise OSError("disk full")

    monkeypatch.setattr(mod.os, "replace", broken_replace)
    with pytest.raises(StorageError, match="Не удалось сохранить файл"):
        repo.add_box("Ящик", "", "")


def test_makedirs_failure_raises_storage_error(data_file):
    import app.storage.excel_repository as mod

    repo = ExcelRepository(str(data_file / "sub" / "inventory.xlsx"))

    def broken_makedirs(path, exist_ok=False):
        raise OSError("no access")

    monkeypatch_os = pytest.MonkeyPatch()
    try:
        monkeypatch_os.setattr(mod.os, "makedirs", broken_makedirs)
        with pytest.raises(StorageError, match="Не удалось создать каталог"):
            repo.load_boxes()
    finally:
        monkeypatch_os.undo()


def test_wrong_header_of_locations_and_items_sheets_is_fixed(repo, data_file):
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.title = "Места"
    ws.append(["Старая", "Шапка"])
    wb.create_sheet("Вещи").append(["Другая", "Шапка"])
    wb.create_sheet("Ящики")
    wb.save(data_file)

    assert list(repo.load_locations().columns) == LOCATION_FIELDS
    assert list(repo.load_items().columns) == ITEM_FIELDS
    assert read_sheet(data_file, "Места")[0] == LOCATION_FIELDS
    assert read_sheet(data_file, "Вещи")[0] == ITEM_FIELDS


def test_delete_missing_box_fails(repo):
    with pytest.raises(StorageError, match="Ящик с ID nope не найден"):
        repo.delete_box("nope")


def test_short_and_idless_rows_are_handled(repo, data_file):
    # Строка короче шапки: недостающие ячейки читаются как пустые строки;
    # строка без ID — пропускается.
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.title = "Ящики"
    ws.append(BOX_FIELDS)
    ws.append(["box1", "Ящик без описания"])  # короче шапки
    ws.append([" ", "без ID"])               # пустой ID — пропустить
    ws.append([None, None, None, None, None]) # полностью пустая строка
    wb.save(data_file)

    boxes = repo.load_boxes()
    assert len(boxes) == 1
    assert boxes.iloc[0]["ID"] == "box1"
    assert boxes.iloc[0]["Место_ID"] == ""
    assert boxes.iloc[0]["Описание"] == ""


def test_backup_failure_raises_storage_error(repo, data_file):
    import app.storage.excel_repository as mod

    def broken_copy2(src, dst):
        raise OSError("read-only")

    repo.load_boxes()  # файл создан
    import shutil

    orig_copy2 = shutil.copy2
    monkeypatch_shutil = pytest.MonkeyPatch()
    try:
        monkeypatch_shutil.setattr(mod.shutil, "copy2", broken_copy2)
        with pytest.raises(StorageError, match="Не удалось создать резервную копию"):
            repo.backup_file()
    finally:
        monkeypatch_shutil.undo()
    assert orig_copy2 is shutil.copy2


def test_load_missing_file_race_raises_storage_error(repo, monkeypatch):
    import app.storage.excel_repository as mod

    def broken_load(path):
        raise FileNotFoundError(path)

    monkeypatch.setattr(mod, "load_workbook", broken_load)
    with pytest.raises(StorageError, match="Файл данных не найден"):
        repo.load_boxes()
