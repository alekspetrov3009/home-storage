"""Роутер управления пользователями (только роль «администратор»).

Весь роутер закрыт зависимостью ``require_admin``: перечислить учётные
записи, создать с любой ролью, отредактировать (логин, пароль, роль,
блокировка) или удалить. Последнего действующего администратора защищает
сервис (400), проверка роли выполняется на сервере для каждого запроса.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Response

from app.api.deps import require_admin
from app.api.schemas import UserCreate, UserOut, UserUpdate, user_out
from app.context import get_auth_service

router = APIRouter(prefix="/api/users", tags=["users"], dependencies=[Depends(require_admin)])


@router.get("", response_model=list[UserOut])
def list_users() -> list[UserOut]:
    """Все учётные записи (без хешей паролей)."""
    return [user_out(user) for user in get_auth_service().list_users()]


@router.post("", response_model=UserOut, status_code=201)
def create_user(payload: UserCreate) -> UserOut:
    """Создаёт учётную запись с любой ролью; занятый логин — 409."""
    user = get_auth_service().create_user(payload.login, payload.password, payload.role)
    return user_out(user)


@router.patch("/{user_id}", response_model=UserOut)
def update_user(user_id: str, payload: UserUpdate) -> UserOut:
    """Частичное обновление: логин, пароль (пустой — не менять), роль, блокировка.

    Понижение или блокировка последнего администратора — 400; занятый
    логин — 409.
    """
    user = get_auth_service().update_user(user_id, payload.model_dump())
    return user_out(user)


@router.delete("/{user_id}", status_code=204, response_class=Response)
def delete_user(user_id: str) -> Response:
    """Удаляет учётную запись вместе с её сессиями; последний
    администратор защищён (400)."""
    get_auth_service().delete_user(user_id)
    return Response(status_code=204)
