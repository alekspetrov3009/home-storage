"""Пользователи и роли: константы, модель и валидация входных данных.

Роль хранится на листе «Пользователи» по-русски («администратор»/«просмотр»),
как значения листа «Корзина»; на границе API она переводится в английские
слаги ``admin``/``viewer`` (snake_case-контракт API). Тексты ошибок валидации —
пользовательский контракт.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.domain.errors import ValidationError

ROLE_ADMIN = "администратор"
ROLE_VIEWER = "просмотр"

# Роли, которые может назначить администратор (порядок = порядок в UI).
ROLES = (ROLE_ADMIN, ROLE_VIEWER)

# Роль ↔ слаг API.
ROLE_SLUGS = {ROLE_ADMIN: "admin", ROLE_VIEWER: "viewer"}
SLUG_ROLES = {slug: role for role, slug in ROLE_SLUGS.items()}

LOGIN_MIN = 3
LOGIN_MAX = 32
PASSWORD_MIN = 6
PASSWORD_MAX = 128

# Буквы/цифры/подчёркивание/точка/дефис, без пробелов и «@» (не e-mail).
_LOGIN_RE = re.compile(r"^[\w.\-]+$", re.UNICODE)


def role_slug(role: str) -> str:
    """Роль листа → слаг API; неизвестная роль возвращается как есть."""
    return ROLE_SLUGS.get(role, role)


def role_from_slug(slug: str) -> str:
    """Слаг API → роль листа; неизвестный слаг — ValidationError."""
    role = SLUG_ROLES.get(str(slug).strip().lower())
    if role is None:
        allowed = ", ".join(ROLE_SLUGS[s] for s in (ROLE_ADMIN, ROLE_VIEWER))
        raise ValidationError(f"Неизвестная роль «{slug}». Доступны: {allowed}.")
    return role


@dataclass(frozen=True)
class User:
    """Учётная запись пользователя склада."""

    id: str
    login: str
    role: str = ROLE_VIEWER
    blocked: bool = False
    created_at: str = ""

    @property
    def is_admin(self) -> bool:
        return self.role == ROLE_ADMIN


def validate_login(login: str) -> str:
    """Логин: 3–32 символа, буквы/цифры и «_.-», без пробелов. Возвращает очищенный."""
    clean = str(login or "").strip()
    if not LOGIN_MIN <= len(clean) <= LOGIN_MAX:
        raise ValidationError(
            f"Логин должен содержать от {LOGIN_MIN} до {LOGIN_MAX} символов."
        )
    if not _LOGIN_RE.fullmatch(clean):
        raise ValidationError(
            "Логин может содержать только буквы, цифры и символы «_», «.», «-» "
            "(без пробелов)."
        )
    return clean


def validate_password(password: str) -> str:
    """Пароль: минимум 6 символов (верхняя граница — от DoS длинным вводом)."""
    password = str(password or "")
    if not PASSWORD_MIN <= len(password) <= PASSWORD_MAX:
        raise ValidationError(
            f"Пароль должен содержать от {PASSWORD_MIN} до {PASSWORD_MAX} символов."
        )
    return password


def validate_role(role: str) -> str:
    """Роль должна быть одной из ROLES (принимается и слаг API)."""
    if role in ROLES:
        return role
    return role_from_slug(role)
