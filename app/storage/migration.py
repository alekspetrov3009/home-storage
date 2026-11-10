"""Миграция файлов данных старого формата.

В старой версии ящик хранил место хранения свободным текстом (колонка «Место»
на листе «Ящики»). Теперь ящик ссылается на ID места с листа «Места» (колонка
«Место_ID»). Логика переноса вынесена в отдельный модуль и покрыта тестами:
это самый хрупкий код хранилища, поведение сохранено дословно.
"""

from __future__ import annotations

from app.domain.fields import now_str
from app.domain.ids import new_id
from app.storage.schema import (
    BOX_HEADERS,
    LEGACY_BOX_HEADERS,
    LOCATION_HEADERS,
    SHEET_BOXES,
    SHEET_LOCATIONS,
    ensure_worksheet,
)
__all__ = ["migrate_legacy_boxes"]


def migrate_legacy_boxes(wb) -> bool:
    """Переносит старый формат ящиков (текст в колонке "Место") на новый.

    Уникальные значения старой колонки становятся местами хранения,
    одноимённые (без учёта регистра) — склеиваются в одно. Возвращает
    True, если книгу изменили и её нужно сохранить.
    """
    if SHEET_BOXES not in wb.sheetnames:
        return False
    ws = wb[SHEET_BOXES]
    if ws.max_row < 1:
        return False
    header = ["" if c.value is None else str(c.value) for c in ws[1]]
    if header[: len(BOX_HEADERS)] == BOX_HEADERS:
        return False  # уже новый формат
    if header[: len(LEGACY_BOX_HEADERS)] != LEGACY_BOX_HEADERS:
        return False  # неизвестный формат — не рискуем трогать

    # Лист "Места" может ещё не существовать — создаём при необходимости.
    loc_ws, _ = ensure_worksheet(wb, SHEET_LOCATIONS, LOCATION_HEADERS)
    existing: dict[str, str] = {}
    for row in loc_ws.iter_rows(min_row=2, values_only=True):
        if row and row[1] is not None and str(row[1]).strip():
            existing[str(row[1]).strip().lower()] = str(row[0])

    rows: list[list[str]] = []
    for row in ws.iter_rows(min_row=2, values_only=True):
        if row is None or all(v is None or str(v).strip() == "" for v in row):
            continue
        if row[0] is None or str(row[0]).strip() == "":
            continue
        place = str(row[2] or "").strip()
        loc_id = ""
        if place:
            key = place.lower()
            if key not in existing:
                loc_id = new_id()
                existing[key] = loc_id
                loc_ws.append([loc_id, place, "", now_str()])
            else:
                loc_id = existing[key]
        rows.append([str(row[0]), str(row[1] or ""), loc_id, str(row[3] or ""), str(row[4] or "")])

    # Переписываем лист ящиков в новом формате и возвращаем его на первое место.
    del wb[SHEET_BOXES]
    new_ws = wb.create_sheet(SHEET_BOXES)
    new_ws.append(BOX_HEADERS)
    for r in rows:
        new_ws.append(r)
    wb.move_sheet(SHEET_BOXES, offset=-(len(wb.sheetnames) - 1))
    return True
