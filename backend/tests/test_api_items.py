"""Тесты API вещей: CRUD, PATCH-семантика, bulk-операции, поиск, категории."""

from __future__ import annotations

from conftest import make_new_workbook


def seed(data_file):
    """Файл с двумя ящиками и тремя вещами (у itm1 есть отметка «Обновлён»)."""
    make_new_workbook(
        data_file,
        locations=[["loc1", "Гараж", "", ""]],
        boxes=[
            ["box1", "Ящик А", "loc1", "", ""],
            ["box2", "Ящик Б", "", "", ""],
        ],
        items=[
            ["itm1", "Отвёртка", "box1", 3, "Инструменты", "крестовая", "2026-01-01 10:00:00"],
            ["itm2", "Молоток", "box2", 2, "Инструменты", "", "2025-01-01 09:00:00"],
            ["itm3", "Гвозди", "", 100, "Расходники", "", ""],
        ],
    )


# --------------------------------------------------------------------------- #
# Список и фильтры
# --------------------------------------------------------------------------- #


def test_list_items_with_labels(client, data_file):
    seed(data_file)
    response = client.get("/api/items")
    assert response.status_code == 200
    items = response.json()
    assert [i["id"] for i in items] == ["itm1", "itm2", "itm3"]
    assert items[0] == {
        "id": "itm1",
        "name": "Отвёртка",
        "box_id": "box1",
        "box_label": "Ящик А · Гараж",
        "quantity": 3,
        "category": "Инструменты",
        "notes": "крестовая",
        "updated_at": "2026-01-01 10:00:00",
    }
    # Вещь «без ящика»: box_id пуст, подписи нет.
    assert items[2]["box_id"] == "" and items[2]["box_label"] is None


def test_list_items_filters(client, data_file):
    seed(data_file)
    by_box = client.get("/api/items", params={"box_id": "box1"})
    assert [i["id"] for i in by_box.json()] == ["itm1"]
    # Категория без учёта регистра.
    by_category = client.get("/api/items", params={"category": "инструменты"})
    assert [i["id"] for i in by_category.json()] == ["itm1", "itm2"]
    empty = client.get("/api/items", params={"box_id": "nope"})
    assert empty.json() == []


# --------------------------------------------------------------------------- #
# Создание
# --------------------------------------------------------------------------- #


def test_create_item_201_with_normalized_category(client, data_file):
    seed(data_file)
    response = client.post(
        "/api/items",
        json={
            "name": "Пила",
            "box_id": "box2",
            "quantity": 2,
            "category": " инструменты ",
            "notes": "ножовка",
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Пила"
    assert body["box_id"] == "box2" and body["box_label"] == "Ящик Б"
    # Категория сведена к каноническому написанию существующей.
    assert body["category"] == "Инструменты"
    assert body["updated_at"] != ""


def test_create_item_quantity_zero_422(client, data_file):
    # На создании количество ≥ 1 (ge=1) — иначе 422 pydantic.
    response = client.post("/api/items", json={"name": "Пила", "quantity": 0})
    assert response.status_code == 422


def test_create_item_unknown_field_422(client, data_file):
    response = client.post("/api/items", json={"name": "Пила", "oops": 1})
    assert response.status_code == 422


def test_create_item_empty_name_400(client, data_file):
    response = client.post("/api/items", json={"name": "   "})
    assert response.status_code == 400
    assert "Укажите название" in response.json()["detail"]


# --------------------------------------------------------------------------- #
# PATCH: частичные поля и box_id → перенос
# --------------------------------------------------------------------------- #


def test_patch_each_field_and_stamp_updated(client, data_file):
    seed(data_file)
    response = client.patch(
        "/api/items/itm1",
        json={
            "name": "Отвёртка большая",
            "quantity": 0,
            "category": "новое",
            "notes": "заметка",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Отвёртка большая"
    assert body["quantity"] == 0  # на PATCH ноль допустим (ge=0)
    assert body["category"] == "новое"
    assert body["notes"] == "заметка"
    # «Обновлён» проставлен сервисом заново.
    assert body["updated_at"] != "2026-01-01 10:00:00" and body["updated_at"] != ""


def test_patch_negative_quantity_422(client, data_file):
    seed(data_file)
    response = client.patch("/api/items/itm1", json={"quantity": -1})
    assert response.status_code == 422


def test_patch_empty_name_400(client, data_file):
    seed(data_file)
    response = client.patch("/api/items/itm1", json={"name": "   "})
    assert response.status_code == 400


def test_patch_box_id_moves_item(client, data_file):
    seed(data_file)
    response = client.patch("/api/items/itm1", json={"box_id": "box2"})
    assert response.status_code == 200
    body = response.json()
    assert body["box_id"] == "box2" and body["box_label"] == "Ящик Б"
    assert body["updated_at"] != "2026-01-01 10:00:00"


def test_patch_box_id_unknown_404(client, data_file):
    seed(data_file)
    response = client.patch("/api/items/itm1", json={"box_id": "nope"})
    assert response.status_code == 404
    assert "Ящик с ID nope не найден" in response.json()["detail"]


def test_patch_box_id_empty_detaches(client, data_file):
    # Пустой box_id — «без ящика», как выбор «— без ящика —» в формах.
    seed(data_file)
    response = client.patch("/api/items/itm1", json={"box_id": ""})
    assert response.status_code == 200
    body = response.json()
    assert body["box_id"] == "" and body["box_label"] is None


def test_patch_unknown_item_404(client, data_file):
    seed(data_file)
    response = client.patch("/api/items/nope", json={"name": "Х"})
    assert response.status_code == 404


# --------------------------------------------------------------------------- #
# Перенос отдельным эндпоинтом
# --------------------------------------------------------------------------- #


def test_move_endpoint(client, data_file):
    seed(data_file)
    response = client.post("/api/items/itm1/move", json={"box_id": "box2"})
    assert response.status_code == 200
    assert response.json()["box_id"] == "box2"


def test_move_endpoint_unknown_box_404(client, data_file):
    seed(data_file)
    response = client.post("/api/items/itm1/move", json={"box_id": "nope"})
    assert response.status_code == 404


def test_move_endpoint_unknown_item_404(client, data_file):
    seed(data_file)
    response = client.post("/api/items/nope/move", json={"box_id": "box1"})
    assert response.status_code == 404


# --------------------------------------------------------------------------- #
# Удаление: одиночное и массовое
# --------------------------------------------------------------------------- #


def test_delete_item_returns_trash_entry(client, data_file):
    seed(data_file)
    response = client.delete("/api/items/itm1")
    assert response.status_code == 200
    body = response.json()
    assert body["kind"] == "item"
    assert body["id"] == "itm1"
    assert body["name"] == "Отвёртка"
    assert body["parent_id"] == "box1"
    assert body["data"]["Количество"] == 3  # сырой снапшот с русскими ключами
    assert client.delete("/api/items/itm1").status_code == 404


def test_bulk_delete_with_ids_query_dedups(client, data_file):
    seed(data_file)
    response = client.delete("/api/items", params={"ids": "itm1,itm2,itm1,nope"})
    assert response.status_code == 200
    entries = response.json()
    assert [e["kind"] for e in entries] == ["item", "item"]
    assert {e["id"] for e in entries} == {"itm1", "itm2"}  # дубликат и nope пропущены
    assert [i["id"] for i in client.get("/api/items").json()] == ["itm3"]


# --------------------------------------------------------------------------- #
# PUT: bulk-save таблицы
# --------------------------------------------------------------------------- #


def test_put_items_bulk_save_normalizes_and_stamps(client, data_file):
    seed(data_file)
    payload = {
        "items": [
            # Новая строка: пустой ID → новый, мусор в количестве → 0, штамп проставлен.
            {"name": "Пила", "box_id": "box1", "quantity": "два",
             "category": " Инструменты ", "notes": ""},
            # Изменённая строка: штамп «Обновлён» переписывается.
            {"id": "itm1", "name": "Отвёртка", "box_id": "box1", "quantity": 5,
             "category": "инструменты", "notes": "крестовая"},
            # Неизменённая строка: исходная отметка сохраняется.
            {"id": "itm2", "name": "Молоток", "box_id": "box2", "quantity": 2,
             "category": "Инструменты", "notes": ""},
        ],
    }
    response = client.put("/api/items", json=payload)
    assert response.status_code == 200
    assert response.json() == {"saved": 3}

    items = {i["id"]: i for i in client.get("/api/items").json()}
    assert len(items) == 3  # itm3 отсутствовал в таблице — лист перезаписан целиком

    new_id = next(k for k in items if k not in ("itm1", "itm2", "itm3"))
    assert items[new_id]["name"] == "Пила"
    assert items[new_id]["quantity"] == 0
    assert items[new_id]["category"] == "Инструменты"
    assert items[new_id]["updated_at"] != ""

    assert items["itm1"]["quantity"] == 5
    assert items["itm1"]["updated_at"] != "2026-01-01 10:00:00"

    assert items["itm2"]["name"] == "Молоток"
    assert items["itm2"]["updated_at"] == "2025-01-01 09:00:00"


def test_put_items_empty_name_400(client, data_file):
    response = client.put("/api/items", json={"items": [{"name": "  "}]})
    assert response.status_code == 400


def test_put_items_unknown_box_400(client, data_file):
    seed(data_file)
    response = client.put(
        "/api/items", json={"items": [{"name": "Пила", "box_id": "nope"}]}
    )
    assert response.status_code == 400
    assert "Ящик с ID nope не найден" in response.json()["detail"]


# --------------------------------------------------------------------------- #
# Поиск и категории
# --------------------------------------------------------------------------- #


def test_search_matches_name_category_notes_and_box_label(client, data_file):
    seed(data_file)
    by_name = client.get("/api/search", params={"q": "отвёрт"})
    assert [i["id"] for i in by_name.json()] == ["itm1"]
    by_category = client.get("/api/search", params={"q": "расходники"})
    assert [i["id"] for i in by_category.json()] == ["itm3"]
    by_notes = client.get("/api/search", params={"q": "крестовая"})
    assert [i["id"] for i in by_notes.json()] == ["itm1"]
    # Поиск по подписи ящика (box2 — «Ящик Б», без места).
    by_box = client.get("/api/search", params={"q": "ящик б"})
    assert [i["id"] for i in by_box.json()] == ["itm2"]
    # Пустой запрос — все вещи.
    assert len(client.get("/api/search").json()) == 3


def test_categories_sorted_and_unique(client, data_file):
    seed(data_file)
    response = client.get("/api/categories")
    assert response.status_code == 200
    assert response.json() == ["Инструменты", "Расходники"]
