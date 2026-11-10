"""QR-коды ящиков."""

from __future__ import annotations

import io

import qrcode
import streamlit as st

from app.config import get_config


def box_url(box_id: str) -> str:
    """Ссылка на содержимое ящика (для QR-кода и глубоких ссылок).

    Ведёт на страницу «Ящик» (/box?box=<id>). Старые QR-коды, напечатанные
    для прошлой версии (/?box=<id>), тоже работают: страница «Обзор»
    перенаправляет их на «Ящик».
    """
    return f"{_base_url()}/box?box={box_id}"


def _base_url() -> str:
    """Базовый URL приложения.

    Приоритет: настроенный ``BASE_URL``. Если он не задан — адрес, под которым
    приложение открыто в браузере (заголовок ``Host`` текущего запроса): QR
    остаётся рабочим и с компьютера, и с телефона в той же сети. Крайний
    резерв — localhost:8501.
    """
    configured = get_config().base_url
    if configured:
        return configured
    try:
        host = st.context.headers.get("Host")
    except Exception:  # noqa: BLE001 — нет runtime-контекста (запуск не под streamlit)
        host = None
    return f"http://{host}" if host else "http://localhost:8501"


def qr_png(box_id: str) -> bytes:
    """PNG-изображение QR-кода со ссылкой на ящик."""
    img = qrcode.make(box_url(box_id), box_size=8, border=2)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
