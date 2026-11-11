"""Конфигурация приложения из переменных окружения.

Читается один раз при первом обращении (``get_config``). Значения и умолчания
полностью соответствуют прежней версии приложения:

- ``DATA_FILE`` — путь к файлу-хранилищу (по умолчанию /data/inventory.xlsx);
- ``BASE_URL``  — базовый URL для QR-кодов ящиков (без завершающего слэша);
- ``CORS_ORIGINS`` — разрешённые источники фронтенда (через запятую).

Флаги публичного развёртывания (по умолчанию — локальная разработка):

- ``REGISTRATION_MODE`` — ``open|closed``: закрыта ли самостоятельная
  регистрация (учётные записи создаёт администратор). В проде ставится
  ``closed``, первый администратор создаётся CLI-командой
  ``python -m app.bootstrap_admin``;
- ``SECURE_COOKIES`` — ``1``: cookie сессии получает флаг ``secure``
  (обязательно при развёртывании по HTTPS);
- ``DOCS_ENABLED`` — ``0``: отключает ``/docs``, ``/redoc`` и
  ``/openapi.json`` (интерактивные доки не отдаются наружу).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache

REGISTRATION_OPEN = "open"
REGISTRATION_CLOSED = "closed"


def _env_bool(name: str, default: str) -> bool:
    """Правда для ``1/true/yes/on`` (регистр не важен), иначе — False."""
    return os.getenv(name, default).strip().lower() in ("1", "true", "yes", "on")


@dataclass(frozen=True)
class Config:
    """Неизменяемые настройки приложения."""

    data_file: str = "/data/inventory.xlsx"
    base_url: str = ""
    cors_origins: tuple[str, ...] = ("http://localhost:5173",)
    registration_mode: str = REGISTRATION_OPEN
    secure_cookies: bool = False
    docs_enabled: bool = True

    @property
    def registration_open(self) -> bool:
        """Самостоятельная регистрация разрешена."""
        return self.registration_mode == REGISTRATION_OPEN


@lru_cache(maxsize=1)
def get_config() -> Config:
    """Возвращает конфигурацию, читая переменные окружения один раз."""
    raw_origins = os.getenv("CORS_ORIGINS", "")
    # Пустая переменная/пропуски между запятыми игнорируются.
    origins = tuple(
        origin.strip() for origin in raw_origins.split(",") if origin.strip()
    ) or ("http://localhost:5173",)
    # Любое значение, кроме «open», означает закрытую регистрацию
    # (безопасная интерпретация мусорного значения в проде).
    registration = os.getenv("REGISTRATION_MODE", REGISTRATION_OPEN).strip().lower()
    return Config(
        data_file=os.getenv("DATA_FILE", "/data/inventory.xlsx"),
        # Без завершающего слэша: ссылка QR-кода склеивается как BASE_URL/box?box=<id>.
        base_url=os.getenv("BASE_URL", "").rstrip("/"),
        cors_origins=origins,
        registration_mode=registration if registration == REGISTRATION_OPEN else REGISTRATION_CLOSED,
        secure_cookies=_env_bool("SECURE_COOKIES", "0"),
        docs_enabled=_env_bool("DOCS_ENABLED", "1"),
    )
