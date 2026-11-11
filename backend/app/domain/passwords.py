"""Хеширование паролей: PBKDF2-HMAC-SHA256 из стандартной библиотеки.

Формат хранения самоописывающий: ``pbkdf2_sha256$<итерации>$<соль>$<хеш>``
(соль и хеш — hex). Итерации записаны в строке, поэтому при ужесточении
константы старые хеши продолжают проверяться, а новые пишутся сильнее.
Внешних зависимостей нет — только hashlib/hmac/secrets.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets

# OWASP рекомендует не меньше 600 000 итераций PBKDF2-HMAC-SHA256.
PBKDF2_ITERATIONS = 600_000
_ALGORITHM = "pbkdf2_sha256"
_SALT_BYTES = 16


def hash_password(password: str) -> str:
    """Хеширует пароль со случайной солью → строка формата для листа «Пользователи»."""
    salt = secrets.token_hex(_SALT_BYTES)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), bytes.fromhex(salt), PBKDF2_ITERATIONS
    )
    return f"{_ALGORITHM}${PBKDF2_ITERATIONS}${salt}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    """Проверяет пароль против сохранённого хеша (защита от подделки формата).

    Неизвестный формат, мусор или пустая ячейка файла — False, а не исключение:
    файл данных может правиться руками.
    """
    try:
        algorithm, iterations, salt, expected_hex = stored.strip().split("$", 3)
        if algorithm != _ALGORITHM:
            return False
        digest = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), bytes.fromhex(salt), int(iterations)
        )
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(digest.hex(), expected_hex.lower())
