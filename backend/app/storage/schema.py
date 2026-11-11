"""Схема листов файла данных и низкоуровневые хелперы openpyxl/pandas.

Формат файла (три основных листа + корзина и категории, создаваемые лениво):

    Лист "Места":  ID | Название | Описание | Создан
    Лист "Ящики":  ID | Название | Место_ID | Описание | Создан
    Лист "Вещи":   ID | Название | Ящик_ID | Количество | Категория | Заметки | Обновлён

    Лист "Корзина" (появляется при первом удалении):
                   Тип | ID | Название | Данные | Родитель_ID | Дата удаления
    где "Данные" — JSON исходной строки удалённой сущности.

    Лист "Категории" (появляется при первой категории, добавленной в настройках):
                   Название

    Лист "Пользователи" (появляется при первой регистрации):
                   ID | Логин | Хеш_Пароля | Роль | Создан | Заблокирован
    где "Роль" — «администратор»/«просмотр», "Заблокирован" — отметка
    времени блокировки или пустая строка.

    Лист "Сессии" (появляется при первом входе):
                   Токен | ID_Пользователя | Создан
    Живут до выхода пользователя (logout) или удаления учётной записи.
"""

from __future__ import annotations

from typing import Any

import pandas as pd
from openpyxl.workbook.workbook import Workbook
from openpyxl.worksheet.worksheet import Worksheet

from app.domain import fields

SHEET_LOCATIONS = "Места"
SHEET_BOXES = "Ящики"
SHEET_ITEMS = "Вещи"
SHEET_TRASH = "Корзина"
SHEET_CATEGORIES = "Категории"
SHEET_USERS = "Пользователи"
SHEET_SESSIONS = "Сессии"

LOCATION_HEADERS = fields.LOCATION_FIELDS
BOX_HEADERS = fields.BOX_FIELDS
ITEM_HEADERS = fields.ITEM_FIELDS
TRASH_HEADERS = fields.TRASH_FIELDS
CATEGORY_HEADERS = fields.CATEGORY_FIELDS
USER_HEADERS = fields.USER_FIELDS
SESSION_HEADERS = fields.SESSION_FIELDS

# Шапка листа "Ящики" в старом формате (до появления мест хранения).
# Нужна только миграции, наружу не отдаётся.
LEGACY_BOX_HEADERS = ["ID", "Название", "Место", "Описание", "Создан"]


def empty_frame(headers: list[str]) -> pd.DataFrame:
    """Пустой DataFrame с нужными колонками и строковым типом.

    Явный dtype='object' важен: без него pandas создаёт колонки типа float64,
    и последующие строковые операции (.str) падают с AttributeError.
    """
    return pd.DataFrame({h: pd.Series(dtype="object") for h in headers})


def ensure_worksheet(
    wb: Workbook, title: str, headers: list[str]
) -> tuple[Worksheet, bool]:
    """Возвращает лист с нужным именем, создавая его и шапку при необходимости.

    Возвращает (лист, нужно_ли_сохранить). Вызывающий код обязан сохранить книгу,
    если флаг взведён, иначе исправленная шапка останется только в памяти.
    """
    if title not in wb.sheetnames:
        ws = wb.create_sheet(title)
        ws.append(headers)
        return ws, True

    ws = wb[title]
    first_row = [c.value for c in ws[1]] if ws.max_row >= 1 else []
    first_row = ["" if v is None else str(v) for v in first_row]

    if first_row[: len(headers)] != headers and ws.max_row <= 1:
        # Лист пуст (только шапка или вообще ничего) — приводим шапку к ожидаемой.
        for idx, header in enumerate(headers, start=1):
            ws.cell(row=1, column=idx, value=header)
        return ws, True

    return ws, False


def rows_to_frame(ws: Worksheet, headers: list[str]) -> pd.DataFrame:
    """Читает лист в DataFrame, приводя пустые ячейки к пустым строкам."""
    records: list[dict[str, Any]] = []
    for row in ws.iter_rows(min_row=2, values_only=True):
        if row is None or all(v is None or str(v).strip() == "" for v in row):
            continue
        record = {}
        for idx, header in enumerate(headers):
            value = row[idx] if idx < len(row) else None
            record[header] = "" if value is None else value
        if str(record.get("ID", "")).strip() == "":
            continue
        records.append(record)

    if not records:
        return empty_frame(headers)

    df = pd.DataFrame(records, columns=headers)
    # Всё, кроме количества, держим строками — так проще сравнивать и искать.
    for column in headers:
        if column != "Количество":
            df[column] = df[column].astype(str)
    return df


def row_index(ws: Worksheet, record_id: str) -> int | None:
    """Номер строки (1-based) с указанным ID, либо None."""
    for idx, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
        if row and str(row[0]) == str(record_id):
            return idx
    return None
