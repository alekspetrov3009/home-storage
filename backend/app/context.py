"""Точка сборки приложения: связывает конфиг, хранилище и сервисы.

Здесь — единственное место, где создаётся конкретная реализация репозитория.
UI получает готовый ``InventoryService`` через ``get_service()``.
"""

from __future__ import annotations

from app.config import get_config
from app.services.caching import CachedRepository
from app.services.inventory_service import InventoryService
from app.services.repository import InventoryRepository
from app.storage.excel_repository import ExcelRepository

_service: InventoryService | None = None


def build_service(data_file: str | None = None) -> InventoryService:
    """Собирает сервис над Excel-репозиторием с 30-секундным кэшем чтений."""
    if data_file is None:
        data_file = get_config().data_file
    repo: InventoryRepository = CachedRepository(ExcelRepository(data_file))
    return InventoryService(repo)


def get_service() -> InventoryService:
    """Синглтон сервиса на время жизни процесса (как прежние модульные функции)."""
    global _service
    if _service is None:
        _service = build_service()
    return _service
