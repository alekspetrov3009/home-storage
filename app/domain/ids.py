"""Генерация идентификаторов записей."""

from __future__ import annotations

import uuid


def new_id() -> str:
    """Случайный 8-символьный hex-идентификатор (как в первой версии приложения)."""
    return uuid.uuid4().hex[:8]
