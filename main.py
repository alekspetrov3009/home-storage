"""Точка входа приложения.

Правильный запуск:

    streamlit run main.py

Запуск напрямую (``python main.py``) тоже работает: скрипт сам перезапустит
себя через streamlit — в «голом» режиме интерфейс не создаётся и приложение
молча завершалось бы с предупреждениями.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def _under_streamlit_runtime() -> bool:
    """True, если скрипт запущен через ``streamlit run`` (есть runtime-контекст)."""
    try:
        from streamlit.runtime.scriptrunner import get_script_run_ctx

        return get_script_run_ctx() is not None
    except Exception:  # noqa: BLE001 — любой сбой импорта значит «не под streamlit»
        return False


def _ensure_credentials() -> None:
    """При первом запуске создаёт пустой credentials.toml.

    Иначе Streamlit при первом старте показывает в консоли интерактивный
    вопрос про email и ждёт ввода — выглядит как «приложение не запускается».
    Пустой файл эквивалентен нажатию Enter в этом вопросе.
    """
    credentials = Path.home() / ".streamlit" / "credentials.toml"
    if credentials.exists():
        return
    try:
        credentials.parent.mkdir(parents=True, exist_ok=True)
        credentials.write_text('[general]\nemail = ""\n', encoding="utf-8")
    except OSError:
        pass  # не критично: при интерактивном запуске Streamlit просто спросит


if __name__ == "__main__":
    if _under_streamlit_runtime():
        from app.ui.navigation import run

        run()
    else:
        # Bare-режим: перезапускаем себя через streamlit, передавая аргументы
        # (например, --server.port 8503). Переменные окружения (DATA_FILE и
        # др.) наследуются автоматически.
        _ensure_credentials()
        print("Запуск через streamlit (правильный способ: streamlit run main.py)…")
        raise SystemExit(
            subprocess.call(
                # Абсолютный путь: запуск «python C:\path\main.py» из другого
                # каталога иначе резолвит main.py относительно cwd и падает.
                [sys.executable, "-m", "streamlit", "run", str(Path(__file__).resolve()),
                 *sys.argv[1:]]
            )
        )
