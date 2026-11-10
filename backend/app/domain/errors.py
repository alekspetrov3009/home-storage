"""Исключения домена и хранилища.

``StorageError`` — пользовательский контракт: его тексты показываются в
интерфейсе как есть, поэтому формулировки менять нельзя.
"""

from __future__ import annotations


class StorageError(RuntimeError):
    """Ошибка чтения или записи файла-хранилища."""


class ValidationError(StorageError):
    """Нарушение инвариантов доменной модели (пустое имя, плохое количество)."""


class NotFoundError(StorageError):
    """Искомая запись отсутствует в хранилище (в API — 404)."""


class ConflictError(StorageError):
    """Запись конфликтует с уже существующей (дубликат имени; в API — 409)."""
