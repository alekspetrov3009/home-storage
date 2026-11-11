"""Тесты чистой логики категорий: нормализация свободного ввода.

Логика вынесена в домен (``app.domain.categories``), чтобы её можно было
проверять без запуска приложения.
"""

from __future__ import annotations

from app.domain.categories import normalize_category


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
