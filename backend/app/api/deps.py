"""Зависимости FastAPI для разграничения доступа.

Проверка прав выполняется на серверной стороне: cookie с токеном сессии
→ учётная запись → роль. ``require_auth`` закрывает любые данные склада от
неавторизованных (401), ``require_admin`` допускает к мутациям и управлению
пользователями только роль «администратор» (403).
"""

from __future__ import annotations

from fastapi import Depends, Request

from app.context import get_auth_service
from app.domain.errors import AuthError, ForbiddenError
from app.domain.users import User

SESSION_COOKIE = "storage_session"
# Cookie живёт 30 дней, но серверная сессия — до выхода пользователя
# (logout) или удаления учётной записи.
SESSION_COOKIE_MAX_AGE = 60 * 60 * 24 * 30


def get_current_user(request: Request) -> User:
    """Пользователь текущей сессии из cookie; без валидной сессии — 401."""
    token = request.cookies.get(SESSION_COOKIE, "")
    user = get_auth_service().user_for_session(token)
    if user is None:
        raise AuthError("Требуется вход в систему.")
    return user


def require_auth(user: User = Depends(get_current_user)) -> User:
    """Требует любой авторизованной учётной записи (401 — без сессии)."""
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    """Только роль «администратор»; остальным — 403."""
    if not user.is_admin:
        raise ForbiddenError("Доступно только администратору.")
    return user
