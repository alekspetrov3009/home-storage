"""Тесты доменных моделей: инварианты и чтение из строк хранилища."""

from __future__ import annotations

import pytest

from app.domain.errors import ValidationError
from app.domain.ids import new_id
from app.domain.models import Box, Item, Location


class TestIds:
    def test_new_id_is_12_hex_chars(self):
        value = new_id()
        assert len(value) == 12
        int(value, 16)  # hex

    def test_ids_are_unique(self):
        assert len({new_id() for _ in range(200)}) == 200


class TestLocation:
    def test_valid_location(self):
        loc = Location(id="loc1", name=" Гараж ", description="полка")
        assert loc.name == "Гараж"

    def test_empty_name_rejected(self):
        with pytest.raises(ValidationError, match="Укажите название места хранения"):
            Location(id="loc1", name="   ")

    def test_from_row(self):
        loc = Location.from_row({"ID": "loc1", "Название": "Гараж", "Описание": "", "Создан": ""})
        assert loc.id == "loc1"

    def test_from_row_defaults(self):
        loc = Location.from_row({"ID": "loc1", "Название": "Гараж"})
        assert loc.description == ""
        assert loc.created == ""


class TestBox:
    def test_valid_box(self):
        box = Box(id="box1", name="Ящик №1", location_id="loc1")
        assert box.location_id == "loc1"

    def test_from_row(self):
        box = Box.from_row(
            {"ID": "box1", "Название": "Ящик", "Место_ID": "loc1", "Описание": "д", "Создан": ""}
        )
        assert box.location_id == "loc1"
        assert box.description == "д"

    def test_empty_name_rejected(self):
        with pytest.raises(ValidationError, match="Укажите название ящика"):
            Box(id="box1", name="")


class TestItem:
    def test_valid_item(self):
        item = Item(id="itm1", name="Отвёртка", box_id="box1", quantity=3)
        assert item.quantity == 3

    def test_zero_quantity_is_allowed(self):
        # Интерфейс разрешает «убавить до нуля» — инвариант неотрицательный.
        assert Item(id="itm1", name="Гвоздь", box_id="box1", quantity=0).quantity == 0

    @pytest.mark.parametrize("qty", [-1, -100])
    def test_negative_quantity_rejected(self, qty):
        with pytest.raises(ValidationError, match="отрицательным"):
            Item(id="itm1", name="Гвоздь", box_id="box1", quantity=qty)

    @pytest.mark.parametrize("qty", ["3", 3.5, None, True])
    def test_non_int_quantity_rejected(self, qty):
        with pytest.raises(ValidationError, match="целым числом"):
            Item(id="itm1", name="Гвоздь", box_id="box1", quantity=qty)

    def test_empty_name_rejected(self):
        with pytest.raises(ValidationError, match="Укажите название вещи"):
            Item(id="itm1", name="", box_id="box1", quantity=1)

    def test_from_row_coerces_quantity(self):
        item = Item.from_row(
            {"ID": "itm1", "Название": "Гвоздь", "Ящик_ID": "box1", "Количество": 5,
             "Категория": "", "Заметки": "", "Обновлён": ""}
        )
        assert item.quantity == 5
        assert item.notes == ""
