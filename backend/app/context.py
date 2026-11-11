"""Точка сборки приложения: связывает конфиг, хранилище и сервисы.

Здесь — единственное место, где создаётся конкретная реализация репозитория.
UI получает готовый ``InventoryService`` через ``get_service()``.
"""

from __future__ import annotations

from app.config import get_config
from app.services.auth_service import AuthService
from app.services.caching import CachedRepository
from app.services.inventory_service import InventoryService
from app.services.repository import InventoryRepository
from app.storage.excel_repository import ExcelRepository

_service: InventoryService | None = None
_auth_service: AuthService | None = None


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


def build_auth_service(data_file: str | None = None) -> AuthService:
    """Собирает сервис авторизации над тем же Excel-репозиторием.

    Пользователи и сессии идут мимо 30-секундного кэша: проверка доступа на
    каждом запросе обязана видеть актуальные блокировки и роли.
    """
    if data_file is None:
        data_file = get_config().data_file
    return AuthService(CachedRepository(ExcelRepository(data_file)))


def get_auth_service() -> AuthService:
    """Синглтон сервиса авторизации на время жизни процесса."""
    global _auth_service
    if _auth_service is None:
        _auth_service = build_auth_service()
    return _auth_service
