"""Тесты конфигурации и точки сборки (composition root)."""

from __future__ import annotations

from app.config import Config, get_config
from app.context import build_service, get_service
from app.services.caching import CachedRepository
from app.services.inventory_service import InventoryService
from app.storage.excel_repository import ExcelRepository


def test_config_defaults():
    cfg = Config()
    assert cfg.data_file == "/data/inventory.xlsx"
    assert cfg.app_title == "📦 Домашний склад"
    assert cfg.base_url == ""
    assert cfg is not None


def test_config_reads_env(monkeypatch):
    monkeypatch.delenv("DATA_FILE", raising=False)
    monkeypatch.delenv("APP_TITLE", raising=False)
    monkeypatch.delenv("BASE_URL", raising=False)
    # Сброс lru-кэша, чтобы конфиг перечитал окружение.
    get_config.cache_clear()
    monkeypatch.setenv("DATA_FILE", "/tmp/x.xlsx")
    monkeypatch.setenv("APP_TITLE", "Тест")
    monkeypatch.setenv("BASE_URL", "http://host:8501/")  # слэш обрезается
    cfg = get_config()
    assert cfg.data_file == "/tmp/x.xlsx"
    assert cfg.app_title == "Тест"
    assert cfg.base_url == "http://host:8501"
    get_config.cache_clear()


def test_build_service_wires_cached_repository(data_file):
    service = build_service(str(data_file))
    assert isinstance(service, InventoryService)
    assert isinstance(service._repo, CachedRepository)
    # Сборка рабочая: файл создаётся при первом чтении.
    service.load_boxes()
    assert data_file.exists()


def test_get_service_is_singleton():
    assert get_service() is get_service()
