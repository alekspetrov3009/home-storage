"""Роутер аутентификации: регистрация, вход, выход, текущий пользователь,
смена собственного пароля.

Успешные register/login создают сессию и ставят HttpOnly-cookie с токеном;
logout удаляет сессию и cookie. Неавторизованный доступ к данным склада
закрывают зависимости из ``app.api.deps``, а не этот роутер.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response

from app.api.deps import SESSION_COOKIE, SESSION_COOKIE_MAX_AGE, get_current_user
from app.api.schemas import ChangePasswordIn, LoginIn, RegisterIn, UserOut, user_out
from app.config import get_config
from app.context import get_auth_service
from app.domain.errors import ForbiddenError
from app.domain.users import User

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _set_session_cookie(response: Response, token: str) -> None:
    """Ставит cookie сессии: HttpOnly, SameSite=Lax (кросс-порт 5173→8000 —
    один сайт, cookie действует). Флаг ``secure`` включается переменной
    SECURE_COOKIES=1 — обязательно при развёртывании по HTTPS, иначе
    cookie не передаётся только по защищённому соединению."""
    response.set_cookie(
        key=SESSION_COOKIE,
        value=token,
        max_age=SESSION_COOKIE_MAX_AGE,
        httponly=True,
        samesite="lax",
        secure=get_config().secure_cookies,
        path="/",
    )


@router.post("/register", response_model=UserOut, status_code=201)
def register(payload: RegisterIn, response: Response) -> UserOut:
    """Самостоятельная регистрация: роль «просмотр».

    Если учётных записей ещё нет, первая получает роль «администратора»
    (bootstrap: иначе администратора некем создать). Сразу выполняется вход.
    Закрыта (403), когда REGISTRATION_MODE=closed: учётные записи создаёт
    администратор через интерфейс, первый — CLI ``python -m app.bootstrap_admin``.
    """
    if not get_config().registration_open:
        raise ForbiddenError(
            "Регистрация закрыта. Учётные записи создаёт администратор."
        )
    user = get_auth_service().register(payload.login, payload.password)
    _set_session_cookie(response, get_auth_service().create_session(user.id))
    return user_out(user)


@router.post("/login", response_model=UserOut)
def login(payload: LoginIn, response: Response) -> UserOut:
    """Вход по логину и паролю; неверные данные или блокировка — 401."""
    user = get_auth_service().authenticate(payload.login, payload.password)
    _set_session_cookie(response, get_auth_service().create_session(user.id))
    return user_out(user)


@router.post("/logout", status_code=204, response_class=Response)
def logout(request: Request, response: Response) -> Response:
    """Выход: сессия удаляется на сервере, cookie сбрасывается."""
    get_auth_service().delete_session(request.cookies.get(SESSION_COOKIE, ""))
    response.delete_cookie(key=SESSION_COOKIE, path="/")
    return Response(status_code=204)


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)) -> UserOut:
    """Текущий пользователь сессии (роль, блокировка, логин)."""
    return user_out(user)


@router.post("/change-password", response_model=UserOut)
def change_password(
    payload: ChangePasswordIn, request: Request, user: User = Depends(get_current_user)
) -> UserOut:
    """Смена пароля собственной учётной записи (любая роль).

    Текущий пароль подтверждается на сервере, новый хешируется. После
    смены закрываются все сессии пользователя, кроме текущей: другие
    устройства разлогиниваются, здесь можно продолжить работу. Неверный
    текущий пароль или короткий новый — 400.
    """
    updated = get_auth_service().change_password(
        user.id,
        payload.current_password,
        payload.new_password,
        except_token=request.cookies.get(SESSION_COOKIE, ""),
    )
    return user_out(updated)
