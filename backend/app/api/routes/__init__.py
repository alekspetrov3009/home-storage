"""Агрегация роутеров API.

Каждый модуль держит свой ``APIRouter(prefix="/api")``; здесь они
склеиваются в один ``api_router`` для ``include_router`` в ``create_app``.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.routes import boxes, health, items, locations, trash

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(locations.router)
api_router.include_router(boxes.router)
api_router.include_router(items.router)
api_router.include_router(trash.router)
