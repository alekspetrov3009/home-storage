"""Excel-репозиторий: чтение и запись файла данных.

Единственный модуль приложения, импортирующий openpyxl. Детали реализации —
потокобезопасность (``threading.RLock``, т.к. Streamlit выполняет скрипт в
нескольких потоках) и атомарная запись (сначала во временный файл, затем
``os.replace``) — спрятаны внутри класса.
"""

from __future__ import annotations

import json
import os
import shutil
import threading
from datetime import datetime
from typing import Any, Mapping

import pandas as pd
from openpyxl import Workbook, load_workbook
from openpyxl.utils.exceptions import InvalidFileException
from openpyxl.workbook.workbook import Workbook as WorkbookType
from openpyxl.worksheet.worksheet import Worksheet

from app.domain.errors import ConflictError, NotFoundError, StorageError
from app.domain.fields import now_str
from app.domain.ids import new_id
from app.domain.trash import (
    TRASH_KIND_BOX,
    TRASH_KIND_ITEM,
    TRASH_KIND_LOCATION,
    DeletedEntry,
    decode_data,
    encode_data,
    parse_ts,
)
from app.storage import schema
from app.storage.migration import migrate_box_color_column, migrate_legacy_boxes
from app.storage.schema import (
    BOX_HEADERS,
    ITEM_HEADERS,
    LOCATION_HEADERS,
    SHEET_BOXES,
    SHEET_ITEMS,
    SHEET_LOCATIONS,
    SHEET_TRASH,
    TRASH_HEADERS,
    ensure_worksheet,
    rows_to_frame,
)

# Лист-приёмник для восстановленных строк, по типу записи корзины.
_TRASH_TARGETS = {
    TRASH_KIND_ITEM: (SHEET_ITEMS, ITEM_HEADERS),
    TRASH_KIND_BOX: (SHEET_BOXES, BOX_HEADERS),
    TRASH_KIND_LOCATION: (SHEET_LOCATIONS, LOCATION_HEADERS),
}


class ExcelRepository:
    """Хранилище в локальном .xlsx-файле. Потокобезопасно."""

    def __init__(self, data_file: str) -> None:
        self._data_file = data_file
        self._lock = threading.RLock()

    # ------------------------------------------------------------------ #
    # Внутренние операции с книгой (вызывать только под блокировкой)
    # ------------------------------------------------------------------ #

    def _save_workbook(self, wb: WorkbookType) -> None:
        """Атомарно сохраняет книгу: сначала во временный файл, затем подмена.

        Так исключается ситуация, когда приложение упало в момент записи и файл
        остался повреждённым — на диске всегда либо старая, либо новая версия.
        """
        data_file = self._data_file
        directory = os.path.dirname(os.path.abspath(data_file))
        tmp_path = os.path.join(directory, f".{os.path.basename(data_file)}.tmp")
        try:
            wb.save(tmp_path)
            os.replace(tmp_path, data_file)
        except OSError as exc:
            raise StorageError(f"Не удалось сохранить файл «{data_file}»: {exc}") from exc
        finally:
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass

    def _ensure_file(self) -> None:
        """Создаёт файл-хранилище с нужной структурой, если его ещё нет."""
        if os.path.exists(self._data_file):
            return

        directory = os.path.dirname(os.path.abspath(self._data_file))
        try:
            os.makedirs(directory, exist_ok=True)
        except OSError as exc:
            raise StorageError(
                f"Не удалось создать каталог для данных «{directory}»: {exc}"
            ) from exc

        wb = Workbook()
        locations = wb.active
        locations.title = SHEET_LOCATIONS
        locations.append(LOCATION_HEADERS)

        boxes = wb.create_sheet(SHEET_BOXES)
        boxes.append(BOX_HEADERS)

        items = wb.create_sheet(SHEET_ITEMS)
        items.append(ITEM_HEADERS)

        self._save_workbook(wb)

    def _load_workbook(self) -> WorkbookType:
        """Открывает книгу, создавая файл при первом запуске."""
        self._ensure_file()
        try:
            wb = load_workbook(self._data_file)
            changed = migrate_legacy_boxes(wb)
            if migrate_box_color_column(wb):
                changed = True
            if changed:
                self._save_workbook(wb)
            return wb
        except FileNotFoundError as exc:
            raise StorageError(f"Файл данных не найден: {self._data_file}") from exc
        except (InvalidFileException, OSError, KeyError) as exc:
            # BadZipFile тоже попадает сюда через OSError-совместимые исключения openpyxl
            raise StorageError(
                f"Файл «{self._data_file}» повреждён или не является книгой Excel ({exc}). "
                "Восстановите его из резервной копии или удалите, чтобы создать заново."
            ) from exc
        except Exception as exc:  # noqa: BLE001 — повреждённый zip даёт разные типы
            raise StorageError(
                f"Не удалось открыть файл «{self._data_file}»: {exc}. "
                "Если файл повреждён, восстановите его из резервной копии."
            ) from exc

    # ------------------------------------------------------------------ #
    # Корзина
    # ------------------------------------------------------------------ #

    def _append_trash(
        self, wb: WorkbookType, kind: str, record: Mapping[str, Any], parent_id: str
    ) -> None:
        """Добавляет строку в лист «Корзина» (лист создаётся при первом удалении).

        Вызывать только под блокировкой и до удаления строки из основного листа:
        затем книга сохраняется один раз вызывающим кодом.
        """
        trash_ws, _ = ensure_worksheet(wb, SHEET_TRASH, TRASH_HEADERS)
        trash_ws.append(
            [
                kind,
                str(record.get("ID", "")),
                str(record.get("Название", "")),
                encode_data(record),
                str(parent_id or ""),
                now_str(),
            ]
        )

    @staticmethod
    def _sheet_record(ws: Worksheet, row: int, headers: list[str]) -> dict[str, Any]:
        """Значения строки листа в виде словаря «колонка -> значение ячейки»."""
        record: dict[str, Any] = {}
        for idx, header in enumerate(headers, start=1):
            record[header] = ws.cell(row=row, column=idx).value
        return record

    def load_trash(self) -> pd.DataFrame:
        """Содержимое корзины. Пустой фрейм, если лист ещё не создавался —
        сам лист при чтении не создаётся (он появляется лениво, при первом
        удалении)."""
        with self._lock:
            wb = self._load_workbook()
            if SHEET_TRASH not in wb.sheetnames:
                return schema.empty_frame(TRASH_HEADERS)
            ws, dirty = ensure_worksheet(wb, SHEET_TRASH, TRASH_HEADERS)
            if dirty:
                self._save_workbook(wb)
            return rows_to_frame(ws, TRASH_HEADERS)

    def trash_add(self, kind: str, record: Mapping[str, Any], parent_id: str = "") -> None:
        """Добавляет произвольную запись в корзину (без изменения основных листов)."""
        with self._lock:
            wb = self._load_workbook()
            self._append_trash(wb, kind, record, parent_id)
            self._save_workbook(wb)

    def trash_restore(self, kind: str, entity_id: str) -> str:
        """Возвращает запись из корзины на её исходный лист.

        ID не меняются: вещь возвращается с тем же Ящик_ID, поэтому если её
        ящик тоже восстановят, привязка оживёт сама. Возвращает название.
        """
        target = _TRASH_TARGETS.get(kind)
        if target is None:
            raise StorageError(f"Неизвестный тип записи корзины: {kind}")
        sheet_title, headers = target

        with self._lock:
            wb = self._load_workbook()
            trash_ws, _ = ensure_worksheet(wb, SHEET_TRASH, TRASH_HEADERS)

            found_row = None
            for row_idx, row in enumerate(
                trash_ws.iter_rows(min_row=2, values_only=True), start=2
            ):
                if row and str(row[0]) == kind and str(row[1]) == str(entity_id):
                    found_row = row_idx
                    break
            if found_row is None:
                raise NotFoundError(
                    "Запись не найдена в корзине (возможно, уже восстановлена)."
                )

            data = decode_data(trash_ws.cell(row=found_row, column=4).value)
            if not data or not str(data.get("ID", "")).strip():
                # Повреждённая (или пустая) JSON-запись корзины: восстановление
                # добавило бы на целевой лист строку с пустым ID/названием.
                # Ничего не пишем и запись корзины не трогаем.
                raise StorageError(
                    f"Запись корзины повреждена (ID {entity_id}): "
                    "сохранённые данные отсутствуют."
                )
            name = str(data.get("Название", ""))

            target_ws, _ = ensure_worksheet(wb, sheet_title, headers)
            if schema.row_index(target_ws, entity_id) is not None:
                raise StorageError(
                    f"Запись с ID {entity_id} уже существует на листе «{sheet_title}»."
                )

            values = []
            for header in headers:
                value = data.get(header, "")
                if header == "Количество":
                    try:
                        value = int(value or 0)
                    except (TypeError, ValueError):
                        value = 0
                values.append("" if value is None else value)
            target_ws.append(values)

            trash_ws.delete_rows(found_row)
            self._save_workbook(wb)
            return name

    def trash_clear(self) -> int:
        """Полностью опустошает корзину. Возвращает число удалённых записей."""
        with self._lock:
            wb = self._load_workbook()
            if SHEET_TRASH not in wb.sheetnames:
                return 0
            trash_ws, _ = ensure_worksheet(wb, SHEET_TRASH, TRASH_HEADERS)
            count = max(0, trash_ws.max_row - 1)
            if count:
                trash_ws.delete_rows(2, count)
                self._save_workbook(wb)
            return count

    def trash_purge_expired(self, cutoff: datetime) -> int:
        """Удаляет из корзины записи, удалённые раньше cutoff. Возвращает их число.

        Записи с неразбираемой отметкой времени не трогает: их виднее оставить
        для ручного восстановления, чем молча терять.
        """
        with self._lock:
            wb = self._load_workbook()
            if SHEET_TRASH not in wb.sheetnames:
                return 0
            trash_ws, _ = ensure_worksheet(wb, SHEET_TRASH, TRASH_HEADERS)

            expired_rows = [
                row_idx
                for row_idx, row in enumerate(
                    trash_ws.iter_rows(min_row=2, values_only=True), start=2
                )
                if row
                and (deleted_at := parse_ts(row[5] if len(row) > 5 else None)) is not None
                and deleted_at < cutoff
            ]
            # Удаляем снизу вверх: удаление строки сдвигает индексы последующих.
            for row_idx in sorted(expired_rows, reverse=True):
                trash_ws.delete_rows(row_idx)
            if expired_rows:
                self._save_workbook(wb)
            return len(expired_rows)

    # ------------------------------------------------------------------ #
    # Чтение
    # ------------------------------------------------------------------ #

    def load_boxes(self) -> pd.DataFrame:
        with self._lock:
            wb = self._load_workbook()
            ws, dirty = ensure_worksheet(wb, SHEET_BOXES, BOX_HEADERS)
            if dirty:
                self._save_workbook(wb)
            return rows_to_frame(ws, BOX_HEADERS)

    def load_items(self) -> pd.DataFrame:
        with self._lock:
            wb = self._load_workbook()
            ws, dirty = ensure_worksheet(wb, SHEET_ITEMS, ITEM_HEADERS)
            if dirty:
                self._save_workbook(wb)
            return rows_to_frame(ws, ITEM_HEADERS)

    def load_locations(self) -> pd.DataFrame:
        with self._lock:
            wb = self._load_workbook()
            ws, dirty = ensure_worksheet(wb, SHEET_LOCATIONS, LOCATION_HEADERS)
            if dirty:
                self._save_workbook(wb)
            return rows_to_frame(ws, LOCATION_HEADERS)

    # ------------------------------------------------------------------ #
    # Места хранения
    # ------------------------------------------------------------------ #

    def add_location(self, name: str, description: str) -> str:
        """Создаёт место хранения. Одноимённые (без учёта регистра) запрещены."""
        with self._lock:
            wb = self._load_workbook()
            ws, _ = ensure_worksheet(wb, SHEET_LOCATIONS, LOCATION_HEADERS)
            name = name.strip()
            for row in ws.iter_rows(min_row=2, values_only=True):
                if row and row[1] is not None and str(row[1]).strip().lower() == name.lower():
                    raise ConflictError(f"Место хранения «{name}» уже существует.")
            loc_id = new_id()
            ws.append([loc_id, name, description.strip(), now_str()])
            self._save_workbook(wb)
            return loc_id

    def update_location(self, location_id: str, fields: dict[str, Any]) -> None:
        """Точечно обновляет поля места хранения по его ID.

        Переименование соблюдает инвариант создания: одноимённые (без
        учёта регистра) места запрещены, кроме самого себя.
        """
        unknown = set(fields) - set(LOCATION_HEADERS)
        if unknown:
            raise StorageError(f"Неизвестные поля: {', '.join(sorted(unknown))}")

        with self._lock:
            wb = self._load_workbook()
            ws, _ = ensure_worksheet(wb, SHEET_LOCATIONS, LOCATION_HEADERS)
            row = schema.row_index(ws, location_id)
            if row is None:
                raise NotFoundError(f"Место хранения с ID {location_id} не найдено.")

            if "Название" in fields:
                new_name = str(fields["Название"]).strip()
                for other in ws.iter_rows(min_row=2, values_only=True):
                    if (
                        other
                        and other[0] is not None
                        and str(other[0]) != str(location_id)
                        and other[1] is not None
                        and str(other[1]).strip().lower() == new_name.lower()
                    ):
                        raise ConflictError(
                            f"Место хранения «{new_name}» уже существует."
                        )

            for column, value in fields.items():
                ws.cell(row=row, column=LOCATION_HEADERS.index(column) + 1, value=value)
            self._save_workbook(wb)

    def delete_location(self, location_id: str) -> DeletedEntry:
        """Убирает место хранения в корзину.

        Привязанные ящики остаются на листе «Ящики» со старым Место_ID:
        они отображаются как «без места хранения», а восстановление места
        возвращает привязку автоматически (ID не меняются).
        """
        with self._lock:
            wb = self._load_workbook()
            loc_ws, _ = ensure_worksheet(wb, SHEET_LOCATIONS, LOCATION_HEADERS)

            row = schema.row_index(loc_ws, location_id)
            if row is None:
                raise NotFoundError(f"Место хранения с ID {location_id} не найдено.")

            record = self._sheet_record(loc_ws, row, LOCATION_HEADERS)
            self._append_trash(wb, TRASH_KIND_LOCATION, record, parent_id="")
            loc_ws.delete_rows(row)
            self._save_workbook(wb)
            return DeletedEntry.from_row({
                "Тип": TRASH_KIND_LOCATION,
                "ID": location_id,
                "Название": record.get("Название", ""),
                "Данные": encode_data(record),
                "Родитель_ID": "",
                "Дата удаления": "",
            })

    # ------------------------------------------------------------------ #
    # Ящики
    # ------------------------------------------------------------------ #

    def add_box(self, name: str, location_id: str, description: str, color: str = "") -> str:
        """Создаёт ящик, привязав его к месту хранения по ID (пустая строка — без места)."""
        with self._lock:
            wb = self._load_workbook()
            if location_id:
                loc_ws, _ = ensure_worksheet(wb, SHEET_LOCATIONS, LOCATION_HEADERS)
                if schema.row_index(loc_ws, location_id) is None:
                    raise NotFoundError(f"Место хранения с ID {location_id} не найдено.")
            ws, _ = ensure_worksheet(wb, SHEET_BOXES, BOX_HEADERS)
            box_id = new_id()
            ws.append([box_id, name.strip(), location_id, description.strip(), now_str(), color.strip()])
            self._save_workbook(wb)
            return box_id

    def update_box(self, box_id: str, fields: dict[str, Any]) -> None:
        """Точечно обновляет поля ящика по его ID.

        `fields` — словарь вида {"Название": "…", "Место_ID": "…"}.
        Существование места проверяет сервис; содержимое (вещи) не трогается.
        """
        unknown = set(fields) - set(BOX_HEADERS)
        if unknown:
            raise StorageError(f"Неизвестные поля: {', '.join(sorted(unknown))}")

        with self._lock:
            wb = self._load_workbook()
            ws, _ = ensure_worksheet(wb, SHEET_BOXES, BOX_HEADERS)
            row = schema.row_index(ws, box_id)
            if row is None:
                raise NotFoundError(f"Ящик с ID {box_id} не найден.")
            for column, value in fields.items():
                ws.cell(row=row, column=BOX_HEADERS.index(column) + 1, value=value)
            self._save_workbook(wb)

    def delete_box(self, box_id: str) -> DeletedEntry:
        """Убирает ящик в корзину.

        Вещи из ящика остаются на листе «Вещи» нетронутыми (их Ящик_ID
        продолжает указывать на удалённый ящик): они отображаются как
        «без ящика», а восстановление ящика возвращает их на место само.
        """
        with self._lock:
            wb = self._load_workbook()
            boxes_ws, _ = ensure_worksheet(wb, SHEET_BOXES, BOX_HEADERS)

            row = schema.row_index(boxes_ws, box_id)
            if row is None:
                raise NotFoundError(f"Ящик с ID {box_id} не найден.")

            record = self._sheet_record(boxes_ws, row, BOX_HEADERS)
            parent_id = str(record.get("Место_ID", "") or "")
            self._append_trash(wb, TRASH_KIND_BOX, record, parent_id)
            boxes_ws.delete_rows(row)
            self._save_workbook(wb)
            return DeletedEntry.from_row({
                "Тип": TRASH_KIND_BOX,
                "ID": box_id,
                "Название": record.get("Название", ""),
                "Данные": encode_data(record),
                "Родитель_ID": parent_id,
                "Дата удаления": "",
            })

    # ------------------------------------------------------------------ #
    # Вещи
    # ------------------------------------------------------------------ #

    def add_item(self, name: str, box_id: str, qty: int, category: str, notes: str) -> str:
        with self._lock:
            wb = self._load_workbook()
            ws, _ = ensure_worksheet(wb, SHEET_ITEMS, ITEM_HEADERS)
            item_id = new_id()
            ws.append([item_id, name.strip(), box_id, int(qty), category.strip(), notes.strip(), now_str()])
            self._save_workbook(wb)
            return item_id

    def update_item(self, item_id: str, fields: dict[str, Any]) -> None:
        """Точечно обновляет поля вещи по её ID.

        `fields` — словарь вида {"Количество": 3, "Ящик_ID": "a1b2c3d4"}.
        Ключи, которых нет в ITEM_HEADERS, игнорируются.
        """
        unknown = set(fields) - set(ITEM_HEADERS)
        if unknown:
            raise StorageError(f"Неизвестные поля: {', '.join(sorted(unknown))}")

        with self._lock:
            wb = self._load_workbook()
            ws, _ = ensure_worksheet(wb, SHEET_ITEMS, ITEM_HEADERS)
            row = schema.row_index(ws, item_id)
            if row is None:
                raise NotFoundError(f"Вещь с ID {item_id} не найдена (возможно, удалена).")

            for column, value in fields.items():
                ws.cell(row=row, column=ITEM_HEADERS.index(column) + 1, value=value)
            ws.cell(row=row, column=ITEM_HEADERS.index("Обновлён") + 1, value=now_str())
            self._save_workbook(wb)

    def delete_item(self, item_id: str) -> DeletedEntry:
        """Убирает вещь в корзину (исходная строка сохраняется целиком)."""
        with self._lock:
            wb = self._load_workbook()
            ws, _ = ensure_worksheet(wb, SHEET_ITEMS, ITEM_HEADERS)
            row = schema.row_index(ws, item_id)
            if row is None:
                raise NotFoundError(f"Вещь с ID {item_id} не найдена (возможно, уже удалена).")

            record = self._sheet_record(ws, row, ITEM_HEADERS)
            parent_id = str(record.get("Ящик_ID", "") or "")
            self._append_trash(wb, TRASH_KIND_ITEM, record, parent_id)
            ws.delete_rows(row)
            self._save_workbook(wb)
            return DeletedEntry.from_row({
                "Тип": TRASH_KIND_ITEM,
                "ID": item_id,
                "Название": record.get("Название", ""),
                "Данные": encode_data(record),
                "Родитель_ID": parent_id,
                "Дата удаления": "",
            })

    def delete_items(self, item_ids: list[str]) -> list[DeletedEntry]:
        """Убирает несколько вещей в корзину за одно сохранение файла.

        Используется массовым удалением в редакторе таблицы. Отсутствующие
        ID пропускаются (строка могла быть удалена параллельно).
        """
        with self._lock:
            wb = self._load_workbook()
            ws, _ = ensure_worksheet(wb, SHEET_ITEMS, ITEM_HEADERS)

            entries: list[DeletedEntry] = []
            rows_to_delete: list[tuple[int, dict[str, Any], str]] = []
            seen_ids: set[str] = set()
            seen_rows: set[int] = set()
            for item_id in item_ids:
                # Дубликаты ID во входном списке (в файле могли остаться
                # строки-дубли из прежних версий редактора) не должны давать
                # вторую запись в корзине и второй delete_rows той же строки:
                # повторное удаление сдвигает индексы и затирает чужую строку.
                key = str(item_id)
                if key in seen_ids:
                    continue
                seen_ids.add(key)
                row = schema.row_index(ws, item_id)
                if row is None or row in seen_rows:
                    continue
                seen_rows.add(row)
                record = self._sheet_record(ws, row, ITEM_HEADERS)
                parent_id = str(record.get("Ящик_ID", "") or "")
                rows_to_delete.append((row, record, parent_id))

            # Сначала запоминаем строки в корзину, затем удаляем снизу вверх.
            for _row, record, parent_id in rows_to_delete:
                self._append_trash(wb, TRASH_KIND_ITEM, record, parent_id)
                entries.append(
                    DeletedEntry(
                        kind=TRASH_KIND_ITEM,
                        id=str(record.get("ID", "")),
                        name=str(record.get("Название", "")),
                        parent_id=parent_id,
                        deleted_at="",
                        data=dict(record),
                    )
                )
            for row, _record, _parent in sorted(rows_to_delete, key=lambda x: -x[0]):
                ws.delete_rows(row)

            if entries:
                self._save_workbook(wb)
            return entries

    def replace_items(self, df: pd.DataFrame) -> None:
        """Полностью перезаписывает лист «Вещи» содержимым DataFrame.

        Используется редактором таблицы: он отдаёт изменённый набор строк целиком.
        """
        with self._lock:
            wb = self._load_workbook()
            if SHEET_ITEMS in wb.sheetnames:
                del wb[SHEET_ITEMS]
            ws = wb.create_sheet(SHEET_ITEMS)
            ws.append(ITEM_HEADERS)

            for _, row in df.iterrows():
                ws.append(
                    [
                        str(row.get("ID", "")),
                        str(row.get("Название", "")),
                        str(row.get("Ящик_ID", "")),
                        int(row.get("Количество", 0) or 0),
                        str(row.get("Категория", "")),
                        str(row.get("Заметки", "")),
                        str(row.get("Обновлён", "")) or now_str(),
                    ]
                )
            self._save_workbook(wb)

    # ------------------------------------------------------------------ #
    # Обслуживание
    # ------------------------------------------------------------------ #

    def backup_file(self) -> str:
        """Создаёт копию файла рядом с оригиналом и возвращает путь к ней.

        Копия сохраняется с расширением .xlsx, а не .bak: openpyxl и Excel
        отказываются открывать книгу с «неизвестным» расширением, и копию
        нельзя было бы восстановить.
        """
        with self._lock:
            self._ensure_file()
            directory = os.path.dirname(os.path.abspath(self._data_file))
            stem = os.path.splitext(os.path.basename(self._data_file))[0]
            stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            target = os.path.join(directory, f"{stem}.{stamp}.backup.xlsx")
            try:
                shutil.copy2(self._data_file, target)
            except OSError as exc:
                raise StorageError(f"Не удалось создать резервную копию: {exc}") from exc
            return target
