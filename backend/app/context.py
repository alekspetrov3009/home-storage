"""Точка сборки приложения: связывает конфиг, хранилище и сервисы.

Здесь — единственное место, где создаётся конкретная реализация репозитория.
UI получает готовый ``InventoryService`` через ``get_service()``.

Важно: оба сервиса (склад и авторизация) работают над ОДНИМ экземпляром
``ExcelRepository``. Его ``threading.RLock`` — единственная защита от
потерянных обновлений при конкурентных запросах (FastAPI выполняет
sync-эндпоинты в threadpool): запись инвентаря и запись сессии при логине
должны исключать друг друга. Отсюда требование развёртывания — один процесс
uvicorn: блокировка файловая и действует только внутри процесса
(``--workers N`` не поддерживается, см. README).
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
_repository: ExcelRepository | None = None


def build_repository(data_file: str | None = None) -> ExcelRepository:
    """Создаёт Excel-репозиторий над указанным (или конфиг-файлом) данных."""
    if data_file is None:
        data_file = get_config().data_file
    return ExcelRepository(data_file)


def build_service(data_file: str | None = None) -> InventoryService:
    """Собирает сервис над Excel-репозиторием с 30-секундным кэшем чтений."""
    repo: InventoryRepository = CachedRepository(build_repository(data_file))
    return InventoryService(repo)


def get_service() -> InventoryService:
    """Синглтон сервиса на время жизни процесса (как прежние модульные функции)."""
    global _service, _repository
    if _service is None:
        if _repository is None:
            _repository = build_repository()
        _service = InventoryService(CachedRepository(_repository))
    return _service


def build_auth_service(data_file: str | None = None) -> AuthService:
    """Собирает сервис авторизации над Excel-репозиторием.

    Пользователи и сессии идут мимо 30-секундного кэша: проверка доступа на
    каждом запросе обязана видеть актуальные блокировки и роли.
    """
    return AuthService(CachedRepository(build_repository(data_file)))


def get_auth_service() -> AuthService:
    """Синглтон сервиса авторизации на время жизни процесса.

    Репозиторий — тот же, что у ``get_service()``: собственный ``CachedRepository``
    здесь изолирует только кэш чтений, а блокировка записи файла — общая.
    """
    global _auth_service, _repository
    if _auth_service is None:
        if _repository is None:
            _repository = build_repository()
        _auth_service = AuthService(CachedRepository(_repository))
    return _auth_service
