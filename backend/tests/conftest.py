"""Общие фикстуры и генераторы xlsx-фикстур для тестов.

Фикстуры создаются программно через openpyxl — реальные пользовательские
данные в репозиторий не попадают никогда.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import app.context as context
from app.config import get_config
from openpyxl import Workbook, load_workbook

SHEET_LOCATIONS = "Места"
SHEET_BOXES = "Ящики"
SHEET_ITEMS = "Вещи"

LOCATION_HEADERS = ["ID", "Название", "Описание", "Создан"]
BOX_HEADERS = ["ID", "Название", "Место_ID", "Описание", "Создан"]
ITEM_HEADERS = [
    "ID", "Название", "Ящик_ID", "Количество", "Категория", "Заметки", "Обновлён",
]

# Шапка листа "Ящики" в старом формате (до появления мест хранения).
LEGACY_BOX_HEADERS = ["ID", "Название", "Место", "Описание", "Создан"]

# --- Аутентификация в тестах -------------------------------------------------
# Клиент фикстуры — администратор с ФИКСИРОВАННОЙ сессией: генераторы
# фикстур переносят листы «Пользователи»/«Сессии» при перезаписи файла,
# поэтому сессия не умирает от ``make_new_workbook``. Хеш пароля —
# с малым числом итераций (быстро; формат совместим с verify_password).

SESSION_COOKIE = "storage_session"
ADMIN_USER_ID = "usradmin01"
ADMIN_LOGIN = "admin"
ADMIN_PASSWORD = "admin123"
ADMIN_TOKEN = "test-session-token"
USER_HEADERS = ["ID", "Логин", "Хеш_Пароля", "Роль", "Создан", "Заблокирован"]
SESSION_HEADERS = ["Токен", "ID_Пользователя", "Создан"]


def admin_password_hash(password: str = ADMIN_PASSWORD) -> str:
    """Быстрый pbkdf2-хеш для тестов (1000 итераций, совместим с verify_password)."""
    import hashlib

    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes(16), 1000)
    return f"pbkdf2_sha256$1000${bytes(16).hex()}${digest.hex()}"


def seed_admin(data_file: Path) -> None:
    """Создаёт администратора и его сессию в файле данных (напрямую репозиторием)."""
    from app.storage.excel_repository import ExcelRepository

    repo = ExcelRepository(str(data_file))
    repo.add_user(ADMIN_USER_ID, ADMIN_LOGIN, admin_password_hash(), "администратор")
    repo.add_session(ADMIN_TOKEN, ADMIN_USER_ID)


def _carry_auth_sheets(path: Path, wb: Workbook) -> None:
    """Переносит листы «Пользователи»/«Сессии» из существующего файла.

    Перезапись данных фикстурой не должна разлогинивать тестового клиента:
    seeded-администратор и его сессия с фиксированным токеном сохраняются.
    """
    if not path.exists():
        return
    try:
        old = load_workbook(path)
    except Exception:  # noqa: BLE001 — битый файл фикстуры не важен для авторизации
        return
    for title, headers in (("Пользователи", USER_HEADERS), ("Сессии", SESSION_HEADERS)):
        if title not in old.sheetnames:
            continue
        ws = wb.create_sheet(title)
        ws.append(headers)
        for row in old[title].iter_rows(min_row=2, values_only=True):
            if row and any(value is not None for value in row):
                ws.append(list(row))


def make_new_workbook(
    path: Path,
    locations: list[list] | None = None,
    boxes: list[list] | None = None,
    items: list[list] | None = None,
    categories: list[list] | None = None,
) -> Path:
    """Создаёт файл данных в новом (актуальном) формате."""
    wb = Workbook()
    ws = wb.active
    ws.title = SHEET_LOCATIONS
    ws.append(LOCATION_HEADERS)
    for row in locations or []:
        ws.append(row)

    boxes_ws = wb.create_sheet(SHEET_BOXES)
    boxes_ws.append(BOX_HEADERS)
    for row in boxes or []:
        boxes_ws.append(row)

    items_ws = wb.create_sheet(SHEET_ITEMS)
    items_ws.append(ITEM_HEADERS)
    for row in items or []:
        items_ws.append(row)

    if categories is not None:
        # Лист «Категории» создаётся лениво — фикстура задаёт его явно.
        categories_ws = wb.create_sheet("Категории")
        categories_ws.append(["Название"])
        for row in categories:
            categories_ws.append(row)

    _carry_auth_sheets(path, wb)
    wb.save(path)
    return path


def make_legacy_workbook(
    path: Path,
    legacy_boxes: list[list],
    extra_locations: list[list] | None = None,
    items: list[list] | None = None,
) -> Path:
    """Создаёт файл данных в СТАРОМ формате: у ящиков текстовая колонка «Место».

    Лист «Места» может как существовать (extra_locations), так и отсутствовать.
    """
    wb = Workbook()
    if extra_locations is not None:
        ws = wb.active
        ws.title = SHEET_LOCATIONS
        ws.append(LOCATION_HEADERS)
        for row in extra_locations:
            ws.append(row)
        boxes_ws = wb.create_sheet(SHEET_BOXES)
    else:
        # Старый файл мог не иметь листа «Места» вовсе; ящики — первый лист.
        boxes_ws = wb.active
        boxes_ws.title = SHEET_BOXES

    boxes_ws.append(LEGACY_BOX_HEADERS)
    for row in legacy_boxes:
        boxes_ws.append(row)

    items_ws = wb.create_sheet(SHEET_ITEMS)
    items_ws.append(ITEM_HEADERS)
    for row in items or []:
        items_ws.append(row)

    wb.save(path)
    return path


def read_sheet(path: Path, title: str) -> list[list]:
    """Читает лист файла как список строк (values_only)."""
    from openpyxl import load_workbook

    wb = load_workbook(path)
    return [list(row) for row in wb[title].iter_rows(values_only=True)]


@pytest.fixture
def data_file(tmp_path: Path) -> Path:
    """Путь к файлу-хранилищу во временном каталоге."""
    return tmp_path / "inventory.xlsx"


@pytest.fixture
def client(monkeypatch, data_file: Path) -> TestClient:
    """TestClient поверх приложения, нацеленного на tmp-фикстуру данных.

    Перед прогоном сбрасываются конфиг-кэш и синглтоны сервисов, чтобы API
    прочитал tmp-фикстуру, а не данные соседних тестов. Клиент —
    залогиненный администратор (фиксированная сессия ``seed_admin``):
    существующие тесты проверяют логику склада, а не требование входа —
    оно покрыто в ``test_api_auth.py``.
    """
    from app.api.main import app

    monkeypatch.setenv("DATA_FILE", str(data_file))
    get_config.cache_clear()
    context._service = None
    context._auth_service = None
    context._repository = None
    seed_admin(data_file)
    test_client = TestClient(app)
    test_client.cookies.set(SESSION_COOKIE, ADMIN_TOKEN)
    yield test_client
    # Чужие тесты не должны увидеть наши синглтоны и закэшированный конфиг.
    context._service = None
    context._auth_service = None
    context._repository = None
    get_config.cache_clear()
