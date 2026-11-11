"""CLI создания учётной записи администратора.

Нужен на публичном хосте, где саморегистрация закрыта
(``REGISTRATION_MODE=closed``): первый администратор создаётся командой

    python -m app.bootstrap_admin <логин>

(в Docker: ``docker compose exec api python -m app.bootstrap_admin admin``).
Пароль запрашивается интерактивно и не попадает в аргументы команды и историю
shell. Команда работает поверх того же Excel-репозитория, что и приложение:
на пустом складе создаёт первого администратора, на непустом — добавляет ещё
одного (дубликат логина — ошибка, пароль повторно запрашивается при опечатке).
"""

from __future__ import annotations

import getpass
import sys

from app.config import get_config
from app.domain.errors import StorageError, ValidationError
from app.domain.ids import new_id
from app.domain.passwords import hash_password
from app.domain.users import ROLE_ADMIN, validate_login, validate_password
from app.storage.excel_repository import ExcelRepository


def _read_password() -> str:
    """Пароль с терминала без эха; подтверждение отлавливает опечатки.

    ``\\r`` в конце обрезается: при неинтерактивном вводе (docker compose
    exec -T, CI-пайплайны) строка может прийти с возвратом каретки —
    без обрезки пароли «не совпадают» из-за невидимого символа.
    """
    first = getpass.getpass("Пароль (минимум 6 символов): ").rstrip("\r")
    second = getpass.getpass("Повторите пароль: ").rstrip("\r")
    if first != second:
        raise ValidationError("Пароли не совпадают.")
    return first


def create_admin(login: str, password: str) -> str:
    """Создаёт администратора в файле данных; возвращает логин.

    Валидация и хеширование — те же, что при регистрации в AuthService;
    роль всегда «администратор», независимо от заполненности склада.
    """
    clean = validate_login(login)
    validate_password(password)
    repo = ExcelRepository(get_config().data_file)
    existing = repo.load_users()
    if not existing[existing["Логин"].astype(str).str.strip().str.lower() == clean.lower()].empty:
        raise ValidationError(f"Логин «{clean}» уже занят.")
    repo.add_user(new_id(), clean, hash_password(password), ROLE_ADMIN)
    return clean


def main() -> int:
    """Точка входа ``python -m app.bootstrap_admin``. 0 — успех, 1 — ошибка."""
    if len(sys.argv) != 2:
        print("Использование: python -m app.bootstrap_admin <логин>", file=sys.stderr)
        return 1
    try:
        login = create_admin(sys.argv[1], _read_password())
    except (ValidationError, StorageError) as exc:
        print(f"Ошибка: {exc}", file=sys.stderr)
        return 1
    print(f"Администратор «{login}» создан.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
