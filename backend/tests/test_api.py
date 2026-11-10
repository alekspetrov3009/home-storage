"""Тесты REST API: health, сводная статистика, ошибка хранилища → 503.

TestClient (на httpx) гоняет реальный FastAPI-стек без сетевого порта.
Перед прогоном сбрасываются конфиг-кэш и синглтон сервиса, чтобы API
прочитал tmp-фикстуру, а не данные соседних тестов.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import app.context as context
from app.config import get_config
from conftest import make_new_workbook


@pytest.fixture
def client(monkeypatch, data_file: Path) -> TestClient:
    """TestClient поверх приложения, нацеленного на tmp-фикстуру данных."""
    from app.api.main import app

    monkeypatch.setenv("DATA_FILE", str(data_file))
    get_config.cache_clear()
    context._service = None
    yield TestClient(app)
    # Чужие тесты не должны увидеть наш синглтон и закэшированный конфиг.
    context._service = None
    get_config.cache_clear()


def test_health_returns_ok(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_stats_returns_counts_from_fixture(client, data_file):
    make_new_workbook(
        data_file,
        locations=[["loc1", "Гараж", "", "2026-01-01 10:00:00"]],
        boxes=[["box1", "Ящик А", "loc1", "", "2026-01-01 10:00:00"]],
        items=[
            ["itm1", "Отвёртка", "box1", 3, "Инструменты", "", ""],
            ["itm2", "Молоток", "box1", 2, "Инструменты", "", ""],
        ],
    )

    response = client.get("/api/stats")
    assert response.status_code == 200
    assert set(response.json()) == {"boxes", "items", "units", "locations"}
    assert response.json() == {"boxes": 1, "items": 2, "units": 5, "locations": 1}


def test_stats_on_corrupted_file_returns_503_with_contract_text(client, data_file):
    # Файл повреждён: сервис бросает StorageError, API отдаёт 503 с текстом-контрактом.
    data_file.write_bytes(b"not an excel file")
    response = client.get("/api/stats")
    assert response.status_code == 503
    assert str(data_file) in response.json()["detail"]
