"""Схемы API: pydantic-модели и маппинг строк DataFrame → ответы.

Имена полей JSON — английские snake_case; русский формат файла не меняется,
перевод выполняется только на границе API. Слаги корзины (item/box/location)
маппируются на значения листа «Корзина» (вещь/ящик/место); ``data`` записи
корзины — сырой снапшот исходной строки с русскими ключами как есть.
"""

from __future__ import annotations

from typing import Any, Mapping

from pydantic import BaseModel, ConfigDict, Field

from app.domain.colors import pick_box_color
from app.domain.trash import DeletedEntry
from app.domain.users import role_slug
from app.helpers import to_qty

# Тип записи корзины ↔ слаг в URL.
KIND_SLUG = {"вещь": "item", "ящик": "box", "место": "location"}
SLUG_KIND = {slug: kind for kind, slug in KIND_SLUG.items()}


class HealthResponse(BaseModel):
    """Ответ проверки живости API (публичный, без данных склада)."""

    status: str
    registration_open: bool


class StatsResponse(BaseModel):
    """Сводная статистика склада для главной страницы фронтенда."""

    boxes: int
    items: int
    units: int
    locations: int


class LocationOut(BaseModel):
    """Место хранения с числом ящиков."""

    id: str
    name: str
    description: str
    created_at: str
    box_count: int


class BoxOut(BaseModel):
    """Ящик с местом хранения и счётчиками вещей.

    ``location_name`` — None, если ящик «без места хранения».
    ``color`` — цвет карточки: из колонки «Цвет», а для старых ящиков —
    авто-выбор из палитры по ID.
    """

    id: str
    name: str
    location_id: str
    location_name: str | None
    description: str
    created_at: str
    item_count: int
    unit_count: int
    color: str


class BoxDetail(BoxOut):
    """Ящик с вещами внутри (детальная страница)."""

    items: list["ItemOut"]


class ItemOut(BaseModel):
    """Вещь с подписью ящика.

    ``box_label`` — None для «без ящика» (и для вещей с удалённым ящиком);
    при дубликатах имён подпись содержит суффикс « · #xxxx» — это подпись
    селекта, не ID.
    """

    id: str
    name: str
    box_id: str
    box_label: str | None
    quantity: int
    category: str
    notes: str
    updated_at: str


class TrashEntryOut(BaseModel):
    """Запись корзины. ``data`` — сырой dict исходной строки (русские ключи)."""

    id: str
    kind: str
    name: str
    parent_id: str
    deleted_at: str
    data: dict[str, Any]


class TrashResponse(BaseModel):
    """Содержимое корзины и число вычищенных просроченных записей."""

    entries: list[TrashEntryOut]
    purged: int


class RestoredResponse(BaseModel):
    """Название восстановленной записи."""

    name: str


class ClearedResponse(BaseModel):
    """Число записей, удалённых из корзины."""

    deleted: int


class BackupResponse(BaseModel):
    """Путь к созданной резервной копии."""

    path: str


class SavedResponse(BaseModel):
    """Число строк, записанных bulk-save таблицы вещей."""

    saved: int


# --------------------------------------------------------------------------- #
# Входные модели: лишние поля тела запроса — ошибка 422
# --------------------------------------------------------------------------- #


class _Input(BaseModel):
    model_config = ConfigDict(extra="forbid")


class LocationCreate(_Input):
    name: str
    description: str = ""


class LocationUpdate(_Input):
    """Частичное обновление места хранения: None = поле не передано (или null)."""

    name: str | None = None
    description: str | None = None


class BoxCreate(_Input):
    name: str
    location_id: str = ""
    description: str = ""


class BoxUpdate(_Input):
    """Частичное обновление ящика: None = поле не передано (или null).

    Пустая строка/NULL в ``location_id`` — «без места хранения».
    """

    name: str | None = None
    location_id: str | None = None
    description: str | None = None


class ItemCreate(_Input):
    name: str
    box_id: str = ""
    quantity: int = Field(default=1, ge=1)
    category: str = ""
    notes: str = ""


class ItemUpdate(_Input):
    """Частичное обновление: None = поле не передано (или передано null)."""

    name: str | None = None
    quantity: int | None = Field(default=None, ge=0)
    category: str | None = None
    notes: str | None = None
    box_id: str | None = None


class MoveIn(_Input):
    box_id: str


class ItemSaveRow(_Input):
    """Строка bulk-save редактора таблицы.

    ``quantity`` — произвольная ячейка: мусор нормализуется в сервисе через
    ``to_qty`` (как в прежнем редакторе), поэтому тип здесь не ограничивают.
    """

    id: str = ""
    name: str
    box_id: str = ""
    quantity: Any = 0
    category: str = ""
    notes: str = ""


class ItemsReplace(_Input):
    items: list[ItemSaveRow]


class CategoryCreate(_Input):
    name: str


class CategoryUpdate(_Input):
    """Переименование категории: ``name`` — текущее имя, ``new_name`` — новое.

    Категория адресуется телом запроса, а не путём: названия могут содержать
    «/» и любые другие символы.
    """

    name: str
    new_name: str


class CategoryMutationOut(BaseModel):
    """Итог операции над категорией + число вещей с изменившейся категорией."""

    name: str
    items_updated: int


class UserOut(BaseModel):
    """Учётная запись без хеша пароля. ``role`` — слаг: admin/viewer."""

    id: str
    login: str
    role: str
    is_admin: bool
    blocked: bool
    created_at: str


class RegisterIn(_Input):
    """Самостоятельная регистрация (роль всегда «просмотр»)."""

    login: str
    password: str


class LoginIn(_Input):
    """Вход по логину и паролю."""

    login: str
    password: str


class ChangePasswordIn(_Input):
    """Смена пароля текущим пользователем: текущий пароль — для подтверждения."""

    current_password: str
    new_password: str


class UserCreate(_Input):
    """Создание учётной записи администратором; ``role`` — слаг admin/viewer."""

    login: str
    password: str
    role: str = "viewer"


class UserUpdate(_Input):
    """Частичное обновление учётной записи: None = поле не передано.

    Пустой ``password`` (или null) — пароль не менять.
    """

    login: str | None = None
    password: str | None = None
    role: str | None = None
    blocked: bool | None = None


# --------------------------------------------------------------------------- #
# Фабрики: строка DataFrame (или dict) → схема ответа
# --------------------------------------------------------------------------- #


def _text(value: Any) -> str:
    return "" if value is None else str(value)


def location_out(row: Mapping[str, Any], box_count: int) -> LocationOut:
    """Строка листа «Места» → LocationOut."""
    return LocationOut(
        id=_text(row.get("ID")),
        name=_text(row.get("Название")),
        description=_text(row.get("Описание")),
        created_at=_text(row.get("Создан")),
        box_count=box_count,
    )


def box_out(
    row: Mapping[str, Any],
    location_name: str | None,
    item_count: int,
    unit_count: int,
) -> BoxOut:
    """Строка листа «Ящики» → BoxOut."""
    return BoxOut(
        id=_text(row.get("ID")),
        name=_text(row.get("Название")),
        location_id=_text(row.get("Место_ID")),
        location_name=location_name,
        description=_text(row.get("Описание")),
        created_at=_text(row.get("Создан")),
        item_count=item_count,
        unit_count=unit_count,
        color=_text(row.get("Цвет")) or pick_box_color(_text(row.get("ID"))),
    )


def item_out(row: Mapping[str, Any], box_label: str | None) -> ItemOut:
    """Строка листа «Вещи» → ItemOut (количество устойчиво к мусору в файле)."""
    return ItemOut(
        id=_text(row.get("ID")),
        name=_text(row.get("Название")),
        box_id=_text(row.get("Ящик_ID")),
        box_label=box_label,
        quantity=to_qty(row.get("Количество", 0)),
        category=_text(row.get("Категория")),
        notes=_text(row.get("Заметки")),
        updated_at=_text(row.get("Обновлён")),
    )


def trash_entry_out(entry: DeletedEntry) -> TrashEntryOut:
    """DeletedEntry → TrashEntryOut; неизвестный тип остаётся как есть."""
    return TrashEntryOut(
        id=entry.id,
        kind=KIND_SLUG.get(entry.kind, entry.kind),
        name=entry.name,
        parent_id=entry.parent_id,
        deleted_at=entry.deleted_at,
        data=entry.data,
    )


def user_out(user) -> UserOut:
    """Доменный User → UserOut (роль переводится в слаг, хеш не отдаётся)."""
    return UserOut(
        id=user.id,
        login=user.login,
        role=role_slug(user.role),
        is_admin=user.is_admin,
        blocked=user.blocked,
        created_at=user.created_at,
    )
