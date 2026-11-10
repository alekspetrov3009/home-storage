"""Тесты API мест хранения: список со счётчиками, создание, удаление, ошибки."""

from __future__ import annotations

from conftest import make_new_workbook, read_sheet


def test_list_locations_with_box_counts(client, data_file):
    make_new_workbook(
        data_file,
        locations=[
            ["loc1", "Гараж", "Подвал", "2026-01-01 10:00:00"],
            ["loc2", "Кладовка", "", ""],
        ],
        boxes=[
            ["box1", "Ящик А", "loc1", "", ""],
            ["box2", "Ящик Б", "loc1", "", ""],
            ["box3", "Ящик В", "ghost", "", ""],  # чужое место не считается
        ],
    )
    response = client.get("/api/locations")
    assert response.status_code == 200
    assert response.json() == [
        {
            "id": "loc1",
            "name": "Гараж",
            "description": "Подвал",
            "created_at": "2026-01-01 10:00:00",
            "box_count": 2,
        },
        {
            "id": "loc2",
            "name": "Кладовка",
            "description": "",
            "created_at": "",
            "box_count": 0,
        },
    ]


def test_create_location_returns_201_and_persists(client, data_file):
    response = client.post(
        "/api/locations", json={"name": "Балкон", "description": "тёплое"}
    )
    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Балкон"
    assert body["description"] == "тёплое"
    assert body["box_count"] == 0
    assert body["id"]
    # Место реально записано в файл.
    rows = read_sheet(data_file, "Места")
    assert any(row[1] == "Балкон" for row in rows[1:])


def test_create_location_empty_name_400(client, data_file):
    response = client.post("/api/locations", json={"name": "   "})
    assert response.status_code == 400
    assert "Укажите название" in response.json()["detail"]


def test_create_location_unknown_field_422(client, data_file):
    # extra="forbid": лишние поля тела запроса не проходят молча.
    response = client.post("/api/locations", json={"name": "Балкон", "extra": 1})
    assert response.status_code == 422


def test_create_location_duplicate_name_409_with_contract_text(client, data_file):
    make_new_workbook(data_file, locations=[["loc1", "Гараж", "", ""]])
    response = client.post("/api/locations", json={"name": "гараж"})
    assert response.status_code == 409
    assert "уже существует" in response.json()["detail"]


def test_delete_location_returns_trash_entry(client, data_file):
    make_new_workbook(data_file, locations=[["loc1", "Гараж", "описание", ""]])
    response = client.delete("/api/locations/loc1")
    assert response.status_code == 200
    body = response.json()
    assert body["kind"] == "location"
    assert body["id"] == "loc1"
    assert body["name"] == "Гараж"
    # data — сырой снапшот исходной строки с русскими ключами.
    assert body["data"]["Описание"] == "описание"
    assert client.get("/api/locations").json() == []
    # Повторное удаление — 404.
    assert client.delete("/api/locations/loc1").status_code == 404
    assert "не найдено" in client.delete("/api/locations/loc1").json()["detail"]


def test_patch_location_name_and_description(client, data_file):
    make_new_workbook(
        data_file,
        locations=[["loc1", "Гараж", "старое описание", ""]],
        boxes=[["box1", "Ящик А", "loc1", "", ""]],
    )
    response = client.patch(
        "/api/locations/loc1", json={"name": "Гараж-2", "description": "новое описание"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Гараж-2"
    assert body["description"] == "новое описание"
    # Счётчик ящиков не потерялся при переименовании.
    assert body["box_count"] == 1
    # Изменения видны и в списке (кэш сброшен).
    assert client.get("/api/locations").json()[0]["name"] == "Гараж-2"


def test_patch_location_duplicate_name_409_with_contract_text(client, data_file):
    make_new_workbook(
        data_file,
        locations=[["loc1", "Гараж", "", ""], ["loc2", "Кладовка", "", ""]],
    )
    response = client.patch("/api/locations/loc1", json={"name": "кладовка"})
    assert response.status_code == 409
    assert "уже существует" in response.json()["detail"]


def test_patch_location_same_name_is_not_duplicate(client, data_file):
    # Переименование в себя (даже в другом регистре) — легально.
    make_new_workbook(data_file, locations=[["loc1", "Гараж", "", ""]])
    response = client.patch("/api/locations/loc1", json={"name": "гараж"})
    assert response.status_code == 200
    assert response.json()["name"] == "гараж"


def test_patch_location_empty_name_400(client, data_file):
    make_new_workbook(data_file, locations=[["loc1", "Гараж", "", ""]])
    response = client.patch("/api/locations/loc1", json={"name": "   "})
    assert response.status_code == 400
    assert "Укажите название" in response.json()["detail"]


def test_patch_location_unknown_404(client, data_file):
    make_new_workbook(data_file)
    response = client.patch("/api/locations/nope", json={"name": "Балкон"})
    assert response.status_code == 404
    assert "не найдено" in response.json()["detail"]


def test_patch_location_extra_field_422(client, data_file):
    make_new_workbook(data_file, locations=[["loc1", "Гараж", "", ""]])
    response = client.patch("/api/locations/loc1", json={"box_count": 5})
    assert response.status_code == 422


def test_patch_location_keeps_box_bindings(client, data_file):
    # Переименование места не трогает ящики: привязка по ID, имя в ответе новое.
    make_new_workbook(
        data_file,
        locations=[["loc1", "Гараж", "", ""]],
        boxes=[["box1", "Ящик А", "loc1", "", ""]],
    )
    client.patch("/api/locations/loc1", json={"name": "Гараж-2"})
    boxes = client.get("/api/boxes").json()
    assert boxes[0]["location_id"] == "loc1"
    assert boxes[0]["location_name"] == "Гараж-2"
