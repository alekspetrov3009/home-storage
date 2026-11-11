"""Тесты QR-кодов ящиков: PNG на месте, неизвестный ящик — 404."""

from __future__ import annotations

from conftest import make_new_workbook

PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def test_qr_returns_png(client, data_file):
    make_new_workbook(data_file, boxes=[["box1", "Ящик А", "", "", ""]])
    response = client.get("/api/boxes/box1/qr")
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert response.content.startswith(PNG_MAGIC)
    assert len(response.content) > 500  # непустой PNG


def test_qr_differs_for_different_boxes(client, data_file):
    make_new_workbook(
        data_file,
        boxes=[["box1", "Ящик А", "", "", ""], ["box2", "Ящик Б", "", "", ""]],
    )
    first = client.get("/api/boxes/box1/qr").content
    second = client.get("/api/boxes/box2/qr").content
    assert first != second  # разные ссылки — разные картинки


def test_qr_unknown_box_404(client, data_file):
    make_new_workbook(data_file)
    response = client.get("/api/boxes/nope/qr")
    assert response.status_code == 404
    assert "Ящик с ID nope не найден" in response.json()["detail"]
