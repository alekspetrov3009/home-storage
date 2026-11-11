"""Сценарии авторизации: регистрация, вход, сессии, управление пользователями.

Работает только через порт ``InventoryRepository`` (методы users/sessions) и
домен (``app.domain.users``, ``app.domain.passwords``). Тексты исключений —
пользовательский контракт.

Роли: «администратор» — полный доступ, включая управление пользователями;
«просмотр» — только чтение данных склада. Самостоятельная регистрация всегда
создаёт роль «просмотр», кроме bootstrap-случая: если учётных записей ещё нет,
первая получает роль «администратора», иначе администратора было бы некем
создать.
"""

from __future__ import annotations

import secrets

import pandas as pd

from app.domain.errors import AuthError, NotFoundError, ValidationError
from app.domain.fields import now_str
from app.domain.ids import new_id
from app.domain.passwords import hash_password, verify_password
from app.domain.users import (
    ROLE_ADMIN,
    ROLE_VIEWER,
    User,
    validate_login,
    validate_password,
    validate_role,
)
from app.services.repository import InventoryRepository


class AuthService:
    """Use-cases пользователей: регистрация, вход/выход, CRUD учётных записей."""

    def __init__(self, repo: InventoryRepository) -> None:
        self._repo = repo

    # ------------------------------------------------------------------ #
    # Внутренние хелперы
    # ------------------------------------------------------------------ #

    def _users(self) -> pd.DataFrame:
        return self._repo.load_users()

    @staticmethod
    def _user_from_row(row: pd.Series) -> User:
        return User(
            id=str(row.get("ID", "")),
            login=str(row.get("Логин", "")),
            role=str(row.get("Роль", "")) or ROLE_VIEWER,
            blocked=bool(str(row.get("Заблокирован", "")).strip()),
            created_at=str(row.get("Создан", "") or ""),
        )

    def _user_by_id(self, user_id: str) -> User:
        users = self._users()
        match = users[users["ID"].astype(str) == str(user_id)]
        if match.empty:
            raise NotFoundError(f"Пользователь с ID {user_id} не найден.")
        return self._user_from_row(match.iloc[0])

    def _active_admins(self) -> list[User]:
        """Администраторы, не заблокированные — те, кто ещё может управлять."""
        return [
            user
            for user in self.list_users()
            if user.is_admin and not user.blocked
        ]

    def _guard_not_last_admin(self, user: User, action: str) -> None:
        """Действие оставит склад без действующего администратора — запрещено."""
        if user.is_admin and not user.blocked and len(self._active_admins()) <= 1:
            raise ValidationError(f"Нельзя {action} последнего администратора.")

    # ------------------------------------------------------------------ #
    # Регистрация и вход
    # ------------------------------------------------------------------ #

    def register(self, login: str, password: str) -> User:
        """Самостоятельная регистрация: роль «просмотр»; первая учётная запись —
        «администратор» (bootstrap). Возвращает созданного пользователя."""
        clean = validate_login(login)
        validate_password(password)
        role = ROLE_VIEWER if not self._users().empty else ROLE_ADMIN
        user = User(id=new_id(), login=clean, role=role)
        self._repo.add_user(user.id, user.login, hash_password(password), user.role)
        return user

    def authenticate(self, login: str, password: str) -> User:
        """Проверяет логин и пароль. Единый текст ошибки — без подсказок,
        существует ли логин. Заблокированная учётная запись не пускается."""
        clean = str(login or "").strip()
        password = str(password or "")
        users = self._users()
        match = users[
            users["Логин"].astype(str).str.strip().str.lower() == clean.lower()
        ]
        if match.empty:
            raise AuthError("Неверный логин или пароль.")
        row = match.iloc[0]
        stored_hash = str(row.get("Хеш_Пароля", "") or "")
        if not stored_hash or not verify_password(password, stored_hash):
            raise AuthError("Неверный логин или пароль.")
        if str(row.get("Заблокирован", "") or "").strip():
            raise AuthError(
                "Учётная запись заблокирована. Обратитесь к администратору."
            )
        return self._user_from_row(row)

    def change_password(
        self, user_id: str, current_password: str, new_password: str, except_token: str = ""
    ) -> User:
        """Смена пароля самим пользователем: текущий пароль подтверждается,
        новый хешируется (PBKDF2, как при регистрации). Возвращает пользователя.

        После смены закрываются все сессии пользователя, кроме текущей
        (except_token): другие устройства разлогиниваются, здесь можно
        продолжить работу. Тексты ошибок — пользовательский контракт
        (показываются в форме смены пароля).
        """
        users = self._users()
        match = users[users["ID"].astype(str) == str(user_id)]
        if match.empty:
            raise NotFoundError(f"Пользователь с ID {user_id} не найден.")
        row = match.iloc[0]
        stored_hash = str(row.get("Хеш_Пароля", "") or "")
        current_password = str(current_password or "")
        if not stored_hash or not verify_password(current_password, stored_hash):
            raise ValidationError("Неверный текущий пароль.")
        new_password = str(new_password or "")
        if new_password == current_password:
            raise ValidationError("Новый пароль совпадает с текущим.")
        validate_password(new_password)
        self._repo.update_user(user_id, {"Хеш_Пароля": hash_password(new_password)})
        self._repo.delete_user_sessions(user_id, except_token)
        return self._user_by_id(user_id)

    # ------------------------------------------------------------------ #
    # Сессии (токен-cookie, живут до выхода или удаления учётной записи)
    # ------------------------------------------------------------------ #

    def create_session(self, user_id: str) -> str:
        """Новый токен сессии для пользователя; сохраняется в файл."""
        token = secrets.token_urlsafe(32)
        self._repo.add_session(token, user_id)
        return token

    def user_for_session(self, token: str) -> User | None:
        """Пользователь активной сессии; None — нет сессии, учётная запись
        удалена или заблокирована (блокировка закрывает сессию сразу)."""
        if not token:
            return None
        record = self._repo.find_session_user(token)
        if record is None:
            return None
        # Ячейка файла может быть None (пустая) — ``or ""`` обязателен:
        # str(None) дал бы «None» и выглядел бы как блокировка.
        user = User(
            id=str(record.get("ID", "")),
            login=str(record.get("Логин", "")),
            role=str(record.get("Роль", "") or "") or ROLE_VIEWER,
            blocked=bool(str(record.get("Заблокирован") or "").strip()),
            created_at=str(record.get("Создан", "") or ""),
        )
        return None if user.blocked else user

    def delete_session(self, token: str) -> None:
        """Выход: сессия удаляется, cookie сбрасывает роутер."""
        self._repo.delete_session(token)

    # ------------------------------------------------------------------ #
    # Управление пользователями (только администратор)
    # ------------------------------------------------------------------ #

    def list_users(self) -> list[User]:
        """Все учётные записи (без хешей), по времени создания."""
        users = [self._user_from_row(row) for _, row in self._users().iterrows()]
        users.sort(key=lambda user: user.login.lower())
        return users

    def create_user(self, login: str, password: str, role: str) -> User:
        """Учётная запись, созданная администратором, с любой ролью."""
        clean = validate_login(login)
        validate_password(password)
        validated_role = validate_role(role)
        user = User(id=new_id(), login=clean, role=validated_role)
        self._repo.add_user(user.id, user.login, hash_password(password), user.role)
        return user

    def update_user(self, user_id: str, fields: dict) -> User:
        """Частичное обновление: логин, пароль, роль, блокировка.

        Защита от потери доступа: нельзя понизить или заблокировать
        последнего действующего администратора.
        """
        current = self._user_by_id(user_id)

        updates: dict[str, str] = {}
        if "login" in fields and fields["login"] is not None:
            updates["Логин"] = validate_login(fields["login"])
        if "password" in fields and fields["password"]:
            validate_password(fields["password"])
            updates["Хеш_Пароля"] = hash_password(fields["password"])
        if "role" in fields and fields["role"] is not None:
            updates["Роль"] = validate_role(fields["role"])
        if "blocked" in fields and fields["blocked"] is not None:
            updates["Заблокирован"] = now_str() if fields["blocked"] else ""

        if updates:
            # Состояние учётной записи после правки: если действующий
            # администратор перестаёт им быть (смена роли или блокировка),
            # он не должен оказаться последним.
            future = User(
                id=current.id,
                login=updates.get("Логин", current.login),
                role=updates.get("Роль", current.role),
                blocked=(
                    bool(updates["Заблокирован"])
                    if "Заблокирован" in updates
                    else current.blocked
                ),
            )
            loses_admin_power = (
                current.is_admin
                and not current.blocked
                and (not future.is_admin or future.blocked)
            )
            if loses_admin_power and len(self._active_admins()) <= 1:
                raise ValidationError(
                    "Нельзя понизить или заблокировать последнего администратора."
                )
            self._repo.update_user(user_id, updates)
        return self._user_by_id(user_id)

    def delete_user(self, user_id: str) -> str:
        """Удаление учётной записи (вместе с её сессиями). Последнего
        действующего администратора удалить нельзя. Возвращает логин."""
        current = self._user_by_id(user_id)
        self._guard_not_last_admin(current, "удалить")
        return self._repo.delete_user(user_id)
