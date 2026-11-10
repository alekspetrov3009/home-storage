"""Схемы ответов API (pydantic-модели)."""

from __future__ import annotations

from pydantic import BaseModel


class HealthResponse(BaseModel):
    """Ответ проверки живости API."""

    status: str


class StatsResponse(BaseModel):
    """Сводная статистика склада для главной страницы фронтенда."""

    boxes: int
    items: int
    units: int
    locations: int
