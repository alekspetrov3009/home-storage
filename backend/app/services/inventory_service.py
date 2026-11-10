"""Сценарии использования: оркестрация репозитория и доменных правил.

UI работает только с этим слоем и никогда не касается репозитория напрямую.
Методы проверяют доменные инварианты через модели из ``app.domain.models``,
затем делегируют запись порту ``InventoryRepository``. Тексты исключений —
пользовательский контракт, совпадают с прежней версией приложения.
"""

from __future__ import annotations

import pandas as pd
from datetime import datetime, timedelta
from typing import Any

from app.domain.categories import unique_categories
from app.domain.errors import ValidationError
from app.domain.ids import new_id
from app.domain.models import Box, Item, Location
from app.domain.trash import TRASH_RETENTION_DAYS, DeletedEntry
from app.services.repository import InventoryRepository


class InventoryService:
    """Use-cases над хранилищем: создание, перенос, удаление, поиск, бэкап."""

    def __init__(self, repo: InventoryRepository) -> None:
        self._repo = repo

    # ------------------------------------------------------------------ #
    # Чтение
    # ------------------------------------------------------------------ #

    def load_boxes(self) -> pd.DataFrame:
        return self._repo.load_boxes()

    def load_items(self) -> pd.DataFrame:
        return self._repo.load_items()

    def load_locations(self) -> pd.DataFrame:
        return self._repo.load_locations()

    def get_categories(self) -> list[str]:
        """Общий список категорий: уникальные значения из всех вещей, по алфавиту.

        Категории не хранятся отдельно — справочник складывается из того,
        что уже используется у вещей, поэтому он одинаковый для всех форм.
        Дубли пишутся без учёта регистра («инструменты» и «Инструменты» —
        одна категория); каноническим считается первое встретившееся
        написание. Тот же алгоритм, что и в формах (см. ``forms.category_options``).
        """
        items = self.load_items()
        if items.empty or "Категория" not in items.columns:
            return []
        return unique_categories(items["Категория"].tolist())

    def clear_cache(self) -> None:
        """Сброс кэша чтений, если репозиторий его поддерживает."""
        clear = getattr(self._repo, "clear_cache", None)
        if callable(clear):
            clear()

    # ------------------------------------------------------------------ #
    # Места хранения
    # ------------------------------------------------------------------ #

    def create_location(self, name: str, description: str) -> str:
        """Создаёт место хранения. Одноимённые (без учёта регистра) запрещены."""
        location = Location(id=new_id(), name=name, description=description)
        return self._repo.add_location(location.name, location.description)

    def delete_location(self, location_id: str) -> DeletedEntry:
        """Убирает место в корзину. Ящики остаются, отображаются как
        «без места хранения»; восстановление места возвращает привязку."""
        return self._repo.delete_location(location_id)

    # ------------------------------------------------------------------ #
    # Ящики
    # ------------------------------------------------------------------ #

    def create_box(self, name: str, location_id: str, description: str) -> str:
        """Создаёт ящик, при необходимости проверяя существование места."""
        box = Box(id=new_id(), name=name, location_id=location_id, description=description)
        return self._repo.add_box(box.name, box.location_id, box.description)

    def delete_box(self, box_id: str) -> DeletedEntry:
        """Убирает ящик в корзину. Вещи остаются (detach), восстановление
        ящика автоматически возвращает вещи с тем же Ящик_ID."""
        return self._repo.delete_box(box_id)

    # ------------------------------------------------------------------ #
    # Вещи
    # ------------------------------------------------------------------ #

    def create_item(self, name: str, box_id: str, qty: int, category: str, notes: str) -> str:
        """Добавляет вещь, проверив доменные инварианты."""
        item = Item(
            id=new_id(),
            name=name,
            box_id=box_id,
            quantity=qty,
            category=category,
            notes=notes,
        )
        return self._repo.add_item(
            item.name, item.box_id, item.quantity, item.category, item.notes
        )

    def update_item(self, item_id: str, fields: dict[str, Any]) -> None:
        """Точечно обновляет поля вещи, валидируя количество и название."""
        if "Количество" in fields:
            # Валидация через модель: целое неотрицательное число.
            Item(
                id=item_id,
                name="проверка",
                box_id="",
                quantity=fields["Количество"],
            )
        if "Название" in fields and not str(fields["Название"] or "").strip():
            raise ValidationError("Укажите название вещи.")
        self._repo.update_item(item_id, fields)

    def move_item(self, item_id: str, target_box_id: str) -> None:
        """Переносит вещь в другой ящик, проверяя, что целевой ящик существует."""
        boxes = self._repo.load_boxes()
        if str(target_box_id) not in boxes["ID"].astype(str).values:
            raise ValidationError(f"Ящик с ID {target_box_id} не найден.")
        self._repo.update_item(item_id, {"Ящик_ID": target_box_id})

    def delete_item(self, item_id: str) -> DeletedEntry:
        """Убирает вещь в корзину (исходная строка сохраняется целиком)."""
        return self._repo.delete_item(item_id)

    def delete_items(self, item_ids: list[str]) -> list[DeletedEntry]:
        """Массово убирает вещи в корзину (редактор таблицы)."""
        return self._repo.delete_items(item_ids)

    def replace_items(self, df: pd.DataFrame) -> None:
        """Полная перезапись листа «Вещи» (редактор таблицы)."""
        self._repo.replace_items(df)

    # ------------------------------------------------------------------ #
    # Поиск
    # ------------------------------------------------------------------ #

    @staticmethod
    def search_item_ids(
        items: pd.DataFrame, box_labels: dict[str, str], query: str
    ) -> list[str]:
        """ID вещей, подходящих под запрос (название, категория, заметки, ящик)."""
        haystack = (
            items["Название"].astype(str).str.lower()
            + " " + items["Категория"].astype(str).str.lower()
            + " " + items["Заметки"].astype(str).str.lower()
            # .astype(str) обязателен: на пустой таблице map() возвращает Series
            # типа float64, и вызов .str падает с AttributeError.
            + items["Ящик_ID"].map(box_labels).fillna("").astype(str).str.lower()
        )
        matched = items[haystack.str.contains(query, regex=False)]
        return matched["ID"].astype(str).tolist()

    # ------------------------------------------------------------------ #
    # Корзина
    # ------------------------------------------------------------------ #

    def load_trash(self) -> pd.DataFrame:
        return self._repo.load_trash()

    def trash_entries(self) -> list[DeletedEntry]:
        """Все записи корзины, новее сверху."""
        trash = self.load_trash()
        entries = [DeletedEntry.from_row(row) for _, row in trash.iterrows()]
        entries.sort(key=lambda e: e.deleted_at, reverse=True)
        return entries

    def restore(self, kind: str, entity_id: str) -> str:
        """Возвращает запись из корзины на исходный лист. Возвращает название.

        Вещь возвращается с прежним Ящик_ID: если её ящик ещё существует —
        она снова в нём; если нет — отображается как «без ящика», и оживёт
        при восстановлении ящика. ID никогда не меняются и не перегенерируются.
        """
        return self._repo.trash_restore(kind, entity_id)

    def clear_trash(self) -> int:
        """Полностью опустошает корзину. Возвращает число удалённых записей."""
        return self._repo.trash_clear()

    def purge_expired_trash(self, now: datetime | None = None) -> int:
        """Вычищает записи старше 30 дней (TRASH_RETENTION_DAYS)."""
        if now is None:
            now = datetime.now()
        cutoff = now - timedelta(days=TRASH_RETENTION_DAYS)
        return self._repo.trash_purge_expired(cutoff)

    # ------------------------------------------------------------------ #
    # Обслуживание
    # ------------------------------------------------------------------ #

    def backup_file(self) -> str:
        return self._repo.backup_file()
