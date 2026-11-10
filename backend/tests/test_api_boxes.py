"""Тесты API ящиков: счётчики, деталь, создание, удаление, QR-маршрут отдельно."""

from __future__ import annotations

from conftest import make_new_workbook


def test_list_boxes_with_counters(client, data_file):
    make_new_workbook(
        data_file,
        locations=[["loc1", "Гараж", "", ""]],
        boxes=[
            ["box1", "Ящик А", "loc1", "", ""],
            ["box2", "Ящик Б", "", "", ""],  # без места
        ],
        items=[
            ["itm1", "Отвёртка", "box1", 3, "", "", ""],
            ["itm2", "Молоток", "box1", 2, "", "", ""],
            ["itm3", "Гвозди", "box2", 100, "", "", ""],
            ["itm4", "Ключ", "ghost", 1, "", "", ""],  # чужой ящик не считается
        ],
    )
    response = client.get("/api/boxes")
    assert response.status_code == 200
    assert response.json() == [
        {
            "id": "box1",
            "name": "Ящик А",
            "location_id": "loc1",
            "location_name": "Гараж",
            "description": "",
            "created_at": "",
            "item_count": 2,
            "unit_count": 5,
        },
        {
            "id": "box2",
            "name": "Ящик Б",
            "location_id": "",
            "location_name": None,
            "description": "",
            "created_at": "",
            "item_count": 1,
            "unit_count": 100,
        },
    ]


def test_get_box_detail_with_items(client, data_file):
    make_new_workbook(
        data_file,
        locations=[["loc1", "Гараж", "", ""]],
        boxes=[["box1", "Ящик А", "loc1", "", ""]],
        items=[
            ["itm1", "Отвёртка", "box1", 3, "", "", ""],
            ["itm2", "Молоток", "box1", 2, "", "", ""],
            ["itm3", "Гвозди", "box2", 1, "", "", ""],
        ],
    )
    response = client.get("/api/boxes/box1")
    assert response.status_code == 200
    body = response.json()
    assert [item["id"] for item in body["items"]] == ["itm1", "itm2"]
    assert body["item_count"] == 2 and body["unit_count"] == 5
    # Подпись ящика в вещах — «Ящик · Место» из box_label_map.
    assert body["items"][0]["box_label"] == "Ящик А · Гараж"


def test_get_box_unknown_404(client, data_file):
    make_new_workbook(data_file)
    response = client.get("/api/boxes/nope")
    assert response.status_code == 404
    assert "Ящик с ID nope не найден" in response.json()["detail"]


def test_create_box_returns_201(client, data_file):
    make_new_workbook(data_file, locations=[["loc1", "Гараж", "", ""]])
    response = client.post(
        "/api/boxes",
        json={"name": "Ящик С", "location_id": "loc1", "description": "новый"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Ящик С"
    assert body["location_name"] == "Гараж"
    assert body["item_count"] == 0 and body["unit_count"] == 0


def test_create_box_with_unknown_location_404(client, data_file):
    # add_box проверяет существование места; StorageError «не найдено» → 404.
    response = client.post("/api/boxes", json={"name": "Ящик", "location_id": "nope"})
    assert response.status_code == 404
    assert "Место хранения с ID nope не найдено" in response.json()["detail"]


def test_create_box_empty_name_400(client, data_file):
    response = client.post("/api/boxes", json={"name": "  "})
    assert response.status_code == 400
    assert "Укажите название" in response.json()["detail"]


def test_delete_box_returns_trash_entry_and_detaches_items(client, data_file):
    make_new_workbook(
        data_file,
        boxes=[["box1", "Ящик А", "loc1", "", ""]],
        items=[["itm1", "Отвёртка", "box1", 3, "", "", ""]],
    )
    response = client.delete("/api/boxes/box1")
    assert response.status_code == 200
    body = response.json()
    assert body["kind"] == "box"
    assert body["id"] == "box1"
    assert body["parent_id"] == "loc1"
    # Вещь осталась, отвязана (подписи ящика больше нет).
    item = client.get("/api/items").json()[0]
    assert item["box_id"] == "box1" and item["box_label"] is None
    # Повторное удаление — 404.
    assert client.delete("/api/boxes/box1").status_code == 404
