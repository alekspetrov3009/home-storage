"""Тесты API корзины, резервной копии и сброса кэша."""

from __future__ import annotations

from pathlib import Path

from openpyxl import load_workbook

from app.domain.fields import TRASH_FIELDS, now_str
from app.domain.trash import encode_data
from conftest import make_new_workbook


def seed(data_file):
    make_new_workbook(
        data_file,
        locations=[["loc1", "Гараж", "", ""]],
        boxes=[["box1", "Ящик А", "loc1", "", ""]],
        items=[["itm1", "Отвёртка", "box1", 3, "", "", ""]],
    )


def append_trash_rows(data_file: Path, rows: list[list]) -> None:
    """Дописывает лист «Корзина» с заданными строками (для теста purge)."""
    wb = load_workbook(data_file)
    ws = wb.create_sheet("Корзина")
    ws.append(TRASH_FIELDS)
    for row in rows:
        ws.append(row)
    wb.save(data_file)


def test_trash_restore_roundtrip_for_all_kinds(client, data_file):
    seed(data_file)
    # Удаляем все три типа через API.
    assert client.delete("/api/items/itm1").status_code == 200
    assert client.delete("/api/boxes/box1").status_code == 200
    assert client.delete("/api/locations/loc1").status_code == 200

    trash = client.get("/api/trash")
    assert trash.status_code == 200
    body = trash.json()
    assert body["purged"] == 0
    assert {e["kind"] for e in body["entries"]} == {"item", "box", "location"}

    # Восстановление в обратном порядке: место → ящик → вещь.
    for kind, entity_id, name in (
        ("location", "loc1", "Гараж"),
        ("box", "box1", "Ящик А"),
        ("item", "itm1", "Отвёртка"),
    ):
        response = client.post(f"/api/trash/{kind}/{entity_id}/restore")
        assert response.status_code == 200
        assert response.json() == {"name": name}

    # Всё вернулось на исходные листы, корзина пуста.
    assert [i["id"] for i in client.get("/api/items").json()] == ["itm1"]
    assert [b["id"] for b in client.get("/api/boxes").json()] == ["box1"]
    assert [l["id"] for l in client.get("/api/locations").json()] == ["loc1"]
    assert client.get("/api/trash").json()["entries"] == []


def test_restore_missing_entry_404(client, data_file):
    seed(data_file)
    response = client.post("/api/trash/item/nope/restore")
    assert response.status_code == 404
    assert "не найдена в корзине" in response.json()["detail"]


def test_restore_unknown_kind_slug_400(client, data_file):
    response = client.post("/api/trash/furniture/nope/restore")
    assert response.status_code == 400
    assert "Неизвестный тип записи корзины" in response.json()["detail"]


def test_trash_purges_expired_entries(client, data_file):
    seed(data_file)
    append_trash_rows(
        data_file,
        [
            # Просроченная запись (старше 30 дней) — вычищается при чтении.
            ["вещь", "old1", "Древний", encode_data({"ID": "old1", "Название": "Древний"}),
             "", "2020-01-01 00:00:00"],
            # Свежая запись — остаётся.
            ["вещь", "fresh1", "Недавний", encode_data({"ID": "fresh1", "Название": "Недавний"}),
             "", now_str()],
        ],
    )
    response = client.get("/api/trash")
    assert response.status_code == 200
    body = response.json()
    assert body["purged"] == 1
    assert [e["id"] for e in body["entries"]] == ["fresh1"]


def test_clear_trash(client, data_file):
    seed(data_file)
    assert client.delete("/api/items/itm1").status_code == 200
    response = client.delete("/api/trash")
    assert response.status_code == 200
    assert response.json() == {"deleted": 1}
    assert client.get("/api/trash").json()["entries"] == []
    # Пустая корзина очищается без ошибки.
    assert client.delete("/api/trash").json() == {"deleted": 0}


def test_backup_creates_file(client, data_file):
    seed(data_file)
    response = client.post("/api/backup")
    assert response.status_code == 200
    path = response.json()["path"]
    assert path.endswith(".backup.xlsx")
    backup = Path(path)
    assert backup.exists() and backup.stat().st_size > 0


def test_cache_clear_returns_204(client, data_file):
    response = client.post("/api/cache/clear")
    assert response.status_code == 204
    assert response.content == b""
