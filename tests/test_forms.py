"""Тесты чистой логики форм: выбор и нормализация категории.

Логика вынесена из виджетов ``app/ui/forms.py`` в чистые функции, чтобы её
можно было проверять без запуска Streamlit.
"""

from __future__ import annotations

import pandas as pd
import pytest

from app.domain.errors import ValidationError
from app.ui.forms import NEW_CATEGORY, category_options, normalize_category, resolve_category


# --------------------------------------------------------------------------- #
# category_options
# --------------------------------------------------------------------------- #


def test_category_options_unique_sorted_without_blanks():
    items = pd.DataFrame({"Категория": ["Инструменты", " инструменты ", "", None, "Разное"]})
    assert category_options(items) == ["Инструменты", "Разное"]


def test_category_options_empty_or_missing_column():
    assert category_options(pd.DataFrame()) == []
    assert category_options(pd.DataFrame({"Название": ["Отвёртка"]})) == []


# --------------------------------------------------------------------------- #
# normalize_category (свободный ввод, таблица вещей)
# --------------------------------------------------------------------------- #


def test_normalize_category_trims_whitespace():
    assert normalize_category("  Инструменты  ", []) == "Инструменты"


def test_normalize_category_empty_means_no_category():
    assert normalize_category("", ["Инструменты"]) == ""
    assert normalize_category("   ", ["Инструменты"]) == ""
    assert normalize_category(None, []) == ""


def test_normalize_category_maps_case_insensitive_match_to_canonical():
    options = ["Инструменты", "Кухня"]
    assert normalize_category("инструменты", options) == "Инструменты"
    assert normalize_category("КУХНЯ", options) == "Кухня"


def test_normalize_category_keeps_new_value():
    assert normalize_category("Гараж", ["Инструменты"]) == "Гараж"


# --------------------------------------------------------------------------- #
# resolve_category (состояние пикера → итоговое имя)
# --------------------------------------------------------------------------- #


def test_resolve_category_returns_chosen_existing_category():
    options = ["Инструменты", "Кухня"]
    assert resolve_category("Кухня", "", options) == "Кухня"


def test_resolve_category_empty_choice_means_no_category():
    assert resolve_category("", "что-то", ["Инструменты"]) == ""


def test_resolve_category_new_category_uses_typed_name():
    options = ["Инструменты"]
    assert resolve_category(NEW_CATEGORY, "  Гараж  ", options) == "Гараж"


def test_resolve_category_new_category_dedupes_case_insensitively():
    options = ["Инструменты"]
    assert resolve_category(NEW_CATEGORY, "инструменты", options) == "Инструменты"


@pytest.mark.parametrize("new_name", ["", "   ", None])
def test_resolve_category_new_category_rejects_empty_name(new_name):
    with pytest.raises(ValidationError, match="Укажите название новой категории"):
        resolve_category(NEW_CATEGORY, new_name, ["Инструменты"])
