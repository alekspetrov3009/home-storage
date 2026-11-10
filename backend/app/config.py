"""Конфигурация приложения из переменных окружения.

Читается один раз при первом обращении (``get_config``). Значения и умолчания
полностью соответствуют прежней версии приложения:

- ``DATA_FILE`` — путь к файлу-хранилищу (по умолчанию /data/inventory.xlsx);
- ``APP_TITLE`` — заголовок приложения;
- ``BASE_URL``  — базовый URL для QR-кодов ящиков (без завершающего слэша);
- ``CORS_ORIGINS`` — разрешённые источники фронтенда (через запятую).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache


@dataclass(frozen=True)
class Config:
    """Неизменяемые настройки приложения."""

    data_file: str = "/data/inventory.xlsx"
    app_title: str = "📦 Домашний склад"
    base_url: str = ""
    cors_origins: tuple[str, ...] = ("http://localhost:5173",)


@lru_cache(maxsize=1)
def get_config() -> Config:
    """Возвращает конфигурацию, читая переменные окружения один раз."""
    raw_origins = os.getenv("CORS_ORIGINS", "")
    # Пустая переменная/пропуски между запятыми игнорируются.
    origins = tuple(
        origin.strip() for origin in raw_origins.split(",") if origin.strip()
    ) or ("http://localhost:5173",)
    return Config(
        data_file=os.getenv("DATA_FILE", "/data/inventory.xlsx"),
        app_title=os.getenv("APP_TITLE", "📦 Домашний склад"),
        # Без завершающего слэша: ссылка QR-кода склеивается как BASE_URL/box?box=<id>.
        base_url=os.getenv("BASE_URL", "").rstrip("/"),
        cors_origins=origins,
    )
