"""Тесты API категорий: справочник, добавление, переименование, удаление.

Справочник — объединение листа «Категории» (пополняется через настройки)
и категорий, уже используемых у вещей. Мутации правят справочник и вещи
за одно сохранение файла; «Обновлён» у вещей при этом не трогается.
"""

from __future__ import annotations

from conftest import make_new_workbook, read_sheet

ITEMS = [
    ["it1", "Отвёртка", "box1", 1, "Инструменты", "", ""],
    ["it2", "Молоток", "box1", 1, "инструменты", "", ""],
    ["it3", "Тарелка", "box1", 2, "Посуда", "", ""],
]


def _categories(client):
    return client.get("/api/categories").json()


def test_get_categories_merges_stored_and_used(client, data_file):
    make_new_workbook(
        data_file,
        items=ITEMS,
        categories=[["Книги"]],
    )
    # «Инструменты»/«инструменты» — одна категория (канон — первое написание),
    # «Книги» — сохранённая без вещей, «Посуда» — только у вещей.
    assert _categories(client) == ["Инструменты", "Книги", "Посуда"]


def test_get_categories_empty_file_without_sheet(client, data_file):
    # Лист «Категории» не создан — чтение возвращает пустой список и не создаёт лист.
    make_new_workbook(data_file)
    assert _categories(client) == []
    from openpyxl import load_workbook

    assert "Категории" not in load_workbook(data_file).sheetnames


def test_create_category_201_and_persists(client, data_file):
    response = client.post("/api/categories", json={"name": "  Книги  "})
    assert response.status_code == 201
    assert response.json() == {"name": "Книги", "items_updated": 0}
    # Категория записана на лист и видна в справочнике.
    rows = read_sheet(data_file, "Категории")
    assert rows == [["Название"], ["Книги"]]
    assert _categories(client) == ["Книги"]


def test_create_category_duplicate_409(client, data_file):
    make_new_workbook(data_file, categories=[["Книги"]])
    response = client.post("/api/categories", json={"name": "книги"})
    assert response.status_code == 409
    assert "уже существует" in response.json()["detail"]


def test_create_category_duplicate_of_used_409(client, data_file):
    make_new_workbook(data_file, items=ITEMS)
    response = client.post("/api/categories", json={"name": "ИНСТРУМЕНТЫ"})
    assert response.status_code == 409
    assert "уже существует" in response.json()["detail"]


def test_create_category_empty_name_400(client, data_file):
    response = client.post("/api/categories", json={"name": "   "})
    assert response.status_code == 400
    assert "Укажите название" in response.json()["detail"]


def test_create_category_unknown_field_422(client, data_file):
    response = client.post("/api/categories", json={"name": "Книги", "extra": 1})
    assert response.status_code == 422


def test_rename_category_updates_items(client, data_file):
    make_new_workbook(data_file, items=ITEMS)
    response = client.patch(
        "/api/categories", json={"name": "инструменты", "new_name": "Ручной инструмент"}
    )
    assert response.status_code == 200
    assert response.json() == {"name": "Ручной инструмент", "items_updated": 2}
    # Вещи получили новое написание, регистровый дубль схлопнулся.
    items = {item["id"]: item["category"] for item in client.get("/api/items").json()}
    assert items["it1"] == "Ручной инструмент"
    assert items["it2"] == "Ручной инструмент"
    assert items["it3"] == "Посуда"
    assert _categories(client) == ["Посуда", "Ручной инструмент"]


def test_rename_category_updates_stored_sheet(client, data_file):
    make_new_workbook(data_file, items=ITEMS, categories=[["Инструменты", ], ["Посуда"]])
    response = client.patch(
        "/api/categories", json={"name": "Инструменты", "new_name": "Ручной инструмент"}
    )
    assert response.status_code == 200
    rows = read_sheet(data_file, "Категории")
    assert ["Ручной инструмент"] in rows
    assert ["Инструменты"] not in rows


def test_rename_category_case_only_normalizes_writing(client, data_file):
    make_new_workbook(data_file, items=ITEMS)
    response = client.patch(
        "/api/categories", json={"name": "инструменты", "new_name": "ИНСТРУМЕНТЫ"}
    )
    assert response.status_code == 200
    assert response.json() == {"name": "ИНСТРУМЕНТЫ", "items_updated": 2}
    items = {item["id"]: item["category"] for item in client.get("/api/items").json()}
    assert items["it1"] == "ИНСТРУМЕНТЫ"
    assert items["it2"] == "ИНСТРУМЕНТЫ"


def test_rename_category_unknown_404(client, data_file):
    make_new_workbook(data_file)
    response = client.patch("/api/categories", json={"name": "нет", "new_name": "Книги"})
    assert response.status_code == 404
    assert "не найдена" in response.json()["detail"]


def test_rename_category_to_existing_409(client, data_file):
    make_new_workbook(data_file, items=ITEMS)
    response = client.patch(
        "/api/categories", json={"name": "Инструменты", "new_name": "Посуда"}
    )
    assert response.status_code == 409
    assert "уже существует" in response.json()["detail"]


def test_rename_category_empty_new_name_400(client, data_file):
    make_new_workbook(data_file, items=ITEMS)
    response = client.patch("/api/categories", json={"name": "Инструменты", "new_name": "  "})
    assert response.status_code == 400
    assert "Укажите название" in response.json()["detail"]


def test_rename_category_extra_field_422(client, data_file):
    make_new_workbook(data_file, categories=[["Книги"]])
    response = client.patch(
        "/api/categories", json={"name": "Книги", "new_name": "Чтиво", "extra": 1}
    )
    assert response.status_code == 422


def test_delete_category_clears_items_and_sheet(client, data_file):
    make_new_workbook(
        data_file,
        items=ITEMS,
        boxes=[["box1", "Ящик А", "", "", ""]],
        categories=[["Инструменты"], ["Посуда"]],
    )
    response = client.delete("/api/categories", params={"name": "инструменты"})
    assert response.status_code == 200
    assert response.json() == {"name": "Инструменты", "items_updated": 2}
    items = {item["id"]: item["category"] for item in client.get("/api/items").json()}
    assert items["it1"] == ""
    assert items["it2"] == ""
    assert items["it3"] == "Посуда"
    # Строка удалена с листа справочника.
    rows = read_sheet(data_file, "Категории")
    assert ["Инструменты"] not in rows
    assert ["Посуда"] in rows
    assert _categories(client) == ["Посуда"]


def test_delete_category_without_items(client, data_file):
    make_new_workbook(data_file, categories=[["Книги"]])
    response = client.delete("/api/categories", params={"name": "Книги"})
    assert response.status_code == 200
    assert response.json() == {"name": "Книги", "items_updated": 0}
    assert read_sheet(data_file, "Категории") == [["Название"]]


def test_delete_category_used_only_cleans_items(client, data_file):
    # Категория существует только у вещей (лист «Категории» не создан).
    make_new_workbook(data_file, items=ITEMS)
    response = client.delete("/api/categories", params={"name": "Посуда"})
    assert response.status_code == 200
    assert response.json() == {"name": "Посуда", "items_updated": 1}
    items = {item["id"]: item["category"] for item in client.get("/api/items").json()}
    assert items["it3"] == ""


def test_delete_category_unknown_404(client, data_file):
    make_new_workbook(data_file)
    response = client.delete("/api/categories", params={"name": "нет"})
    assert response.status_code == 404
    assert "не найдена" in response.json()["detail"]


def test_delete_category_empty_name_400(client, data_file):
    make_new_workbook(data_file)
    response = client.delete("/api/categories")
    assert response.status_code == 400
    assert "Укажите название" in response.json()["detail"]


def test_rename_keeps_item_updated_stamp(client, data_file):
    # Переименование категории — операция справочника: «Обновлён» не меняется.
    make_new_workbook(
        data_file,
        items=[["it1", "Отвёртка", "box1", 1, "Инструменты", "", "2026-01-01 10:00:00"]],
    )
    client.patch("/api/categories", json={"name": "Инструменты", "new_name": "Ручное"})
    items = client.get("/api/items").json()
    assert items[0]["updated_at"] == "2026-01-01 10:00:00"
