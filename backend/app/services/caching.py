"""Кэширующая обёртка над репозиторием.

Данные кэшируются на 30 секунд: снижает число чтений файла при частых
запросах API. Кэшируются только чтения; любые операции записи идут напрямую
в базовый репозиторий. После изменений клиент вызывает ``clear_cache()``,
чтобы получить актуальное состояние.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from datetime import datetime
from typing import Any, Mapping

import pandas as pd

from app.services.repository import InventoryRepository
from app.domain.trash import DeletedEntry

_TTL_SECONDS = 30

_READ_METHODS = ("load_boxes", "load_items", "load_locations", "load_trash", "load_categories")


class CachedRepository:
    """Реализует InventoryRepository, кэшируя чтения на 30 секунд."""

    def __init__(self, repo: InventoryRepository) -> None:
        self._repo = repo
        # Кэш чтений: имя метода -> (результат, time.monotonic() записи).
        self._cache: dict[str, tuple[Any, float]] = {}
        self._lock = threading.RLock()

    def _cached_read(self, name: str, read: Callable[[], pd.DataFrame]) -> pd.DataFrame:
        with self._lock:
            entry = self._cache.get(name)
            if entry is not None:
                result, stored_at = entry
                if time.monotonic() - stored_at < _TTL_SECONDS:
                    return result
            result = read()
            self._cache[name] = (result, time.monotonic())
            return result

    # --- Чтение (кэшируется) ------------------------------------------- #

    def load_boxes(self) -> pd.DataFrame:
        return self._cached_read("load_boxes", self._repo.load_boxes)

    def load_items(self) -> pd.DataFrame:
        return self._cached_read("load_items", self._repo.load_items)

    def load_locations(self) -> pd.DataFrame:
        return self._cached_read("load_locations", self._repo.load_locations)

    def load_trash(self) -> pd.DataFrame:
        return self._cached_read("load_trash", self._repo.load_trash)

    def load_categories(self) -> pd.DataFrame:
        return self._cached_read("load_categories", self._repo.load_categories)

    # --- Запись (мимо кэша) --------------------------------------------- #

    def add_location(self, name: str, description: str) -> str:
        return self._repo.add_location(name, description)

    def update_location(self, location_id: str, fields: dict[str, Any]) -> None:
        self._repo.update_location(location_id, fields)

    def delete_location(self, location_id: str) -> DeletedEntry:
        return self._repo.delete_location(location_id)

    def add_box(self, name: str, location_id: str, description: str, color: str = "") -> str:
        return self._repo.add_box(name, location_id, description, color)

    def update_box(self, box_id: str, fields: dict[str, Any]) -> None:
        self._repo.update_box(box_id, fields)

    def delete_box(self, box_id: str) -> DeletedEntry:
        return self._repo.delete_box(box_id)

    def add_item(self, name: str, box_id: str, qty: int, category: str, notes: str) -> str:
        return self._repo.add_item(name, box_id, qty, category, notes)

    def update_item(self, item_id: str, fields: dict[str, Any]) -> None:
        self._repo.update_item(item_id, fields)

    def delete_item(self, item_id: str) -> DeletedEntry:
        return self._repo.delete_item(item_id)

    def delete_items(self, item_ids: list[str]) -> list[DeletedEntry]:
        return self._repo.delete_items(item_ids)

    def replace_items(self, df: pd.DataFrame) -> None:
        self._repo.replace_items(df)

    def add_category(self, name: str) -> None:
        self._repo.add_category(name)

    def rename_category(self, old: str, new: str) -> int:
        return self._repo.rename_category(old, new)

    def delete_category(self, name: str) -> int:
        return self._repo.delete_category(name)

    def trash_add(self, kind: str, record: Mapping[str, Any], parent_id: str = "") -> None:
        self._repo.trash_add(kind, record, parent_id)

    def trash_restore(self, kind: str, entity_id: str) -> str:
        return self._repo.trash_restore(kind, entity_id)

    def trash_clear(self) -> int:
        return self._repo.trash_clear()

    def trash_purge_expired(self, cutoff: datetime) -> int:
        return self._repo.trash_purge_expired(cutoff)

    # --- Пользователи и сессии (мимо кэша: проверка доступа на каждом
    # --- запросе должна видеть актуальное состояние блокировок) --------- #

    def load_users(self) -> pd.DataFrame:
        return self._repo.load_users()

    def add_user(self, user_id: str, login: str, password_hash: str, role: str) -> None:
        self._repo.add_user(user_id, login, password_hash, role)

    def update_user(self, user_id: str, fields: dict[str, Any]) -> None:
        self._repo.update_user(user_id, fields)

    def delete_user(self, user_id: str) -> str:
        return self._repo.delete_user(user_id)

    def add_session(self, token: str, user_id: str) -> None:
        self._repo.add_session(token, user_id)

    def delete_session(self, token: str) -> None:
        self._repo.delete_session(token)

    def find_session_user(self, token: str) -> dict[str, Any] | None:
        return self._repo.find_session_user(token)

    def backup_file(self) -> str:
        return self._repo.backup_file()

    # --- Кэш -------------------------------------------------------------- #

    def clear_cache(self) -> None:
        """Сбрасывает кэш данных после изменений."""
        with self._lock:
            self._cache.clear()
