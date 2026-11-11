"""Тесты флагов публичного развёртывания и защиты от атак.

Закрытая саморегистрация (REGISTRATION_MODE), флаг Secure у cookie сессии
(SECURE_COOKIES), проверка Origin на мутациях (CSRF defense-in-depth),
отключение доков (DOCS_ENABLED) и CLI первого администратора
(app.bootstrap_admin).
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import app.context as context
from conftest import read_sheet, seed_admin
from app.config import get_config


@pytest.fixture
def prod_env(monkeypatch, tmp_path):
    """Чистое окружение с файлом данных во tmp и сбросом конфиг-кэша.

    Аналог fresh_env из test_api_auth.py: env-переменные ставит сам тест
    перед созданием клиента, чтобы get_config() прочитал их заново.
    """
    data_file = tmp_path / "prod.xlsx"
    monkeypatch.setenv("DATA_FILE", str(data_file))
    get_config.cache_clear()
    context._service = None
    context._auth_service = None
    context._repository = None
    yield data_file
    context._service = None
    context._auth_service = None
    context._repository = None
    get_config.cache_clear()


def _fresh_client(app) -> TestClient:
    """TestClient без предзалогиненной сессии (гость)."""
    return TestClient(app)


# --------------------------------------------------------------------------- #
# Закрытая саморегистрация (REGISTRATION_MODE=closed)
# --------------------------------------------------------------------------- #


def test_health_reports_registration_open_by_default(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["registration_open"] is True


def test_register_closed_returns_403_with_contract_text(prod_env, monkeypatch):
    from app.api.main import app

    monkeypatch.setenv("REGISTRATION_MODE", "closed")
    get_config.cache_clear()
    client = _fresh_client(app)

    response = client.post(
        "/api/auth/register", json={"login": "intruder", "password": "parol123"}
    )
    assert response.status_code == 403
    assert "Регистрация закрыта" in response.json()["detail"]

    health = client.get("/api/health")
    assert health.status_code == 200
    assert health.json()["registration_open"] is False


def test_register_closed_garbage_value_is_closed(prod_env, monkeypatch):
    """Мусорное значение переменной трактуется как закрытая регистрация."""
    from app.api.main import app

    monkeypatch.setenv("REGISTRATION_MODE", "yea-whatever")
    get_config.cache_clear()
    client = _fresh_client(app)

    response = client.post(
        "/api/auth/register", json={"login": "intruder", "password": "parol123"}
    )
    assert response.status_code == 403


def test_register_closed_case_insensitive_open(prod_env, monkeypatch):
    from app.api.main import app

    monkeypatch.setenv("REGISTRATION_MODE", "Open")
    get_config.cache_clear()
    client = _fresh_client(app)

    assert client.get("/api/health").json()["registration_open"] is True


# --------------------------------------------------------------------------- #
# Secure-флаг cookie сессии (SECURE_COOKIES)
# --------------------------------------------------------------------------- #


def _login_response(client, login="admin", password="admin123"):
    return client.post("/api/auth/login", json={"login": login, "password": password})


def test_cookie_without_secure_flag_by_default(client):
    response = _login_response(client)
    assert response.status_code == 200
    set_cookie = response.headers["set-cookie"].lower()
    assert "httponly" in set_cookie
    assert "samesite=lax" in set_cookie
    # Токен "secure" не встречается ни как флаг, ни случайно: подстроку
    # ищем в списке атрибутов через "; " границы — простая проверка отсутствия.
    assert "secure" not in [part.strip().split("=")[0] for part in set_cookie.split(";")]


def test_cookie_secure_flag_enabled(prod_env, monkeypatch):
    from app.api.main import app

    monkeypatch.setenv("SECURE_COOKIES", "1")
    get_config.cache_clear()
    seed_admin(prod_env)
    client = _fresh_client(app)

    response = _login_response(client)
    assert response.status_code == 200
    set_cookie = response.headers["set-cookie"].lower()
    assert "secure" in [part.strip().split("=")[0] for part in set_cookie.split(";")]


# --------------------------------------------------------------------------- #
# Origin-проверка мутаций (CSRF defense-in-depth)
# --------------------------------------------------------------------------- #


def test_mutation_with_foreign_origin_rejected(prod_env):
    from app.api.main import app

    seed_admin(prod_env)
    client = _fresh_client(app)
    response = client.post(
        "/api/auth/login",
        json={"login": "admin", "password": "admin123"},
        headers={"Origin": "https://evil.example"},
    )
    assert response.status_code == 403
    assert "источник не разрешён" in response.json()["detail"]


def test_mutation_with_own_host_origin_allowed(prod_env):
    """Origin, совпадающий с Host запроса (обычный same-origin браузера), проходит."""
    from app.api.main import app

    seed_admin(prod_env)
    client = _fresh_client(app)
    response = client.post(
        "/api/auth/login",
        json={"login": "admin", "password": "admin123"},
        headers={"Origin": "http://testserver"},
    )
    assert response.status_code == 200


def test_mutation_with_cors_origin_allowed(prod_env, monkeypatch):
    """Origin из CORS_ORIGINS (кросс-порт разработки 5173→8000) проходит."""
    from app.api.main import app

    monkeypatch.setenv("CORS_ORIGINS", "http://localhost:5173")
    get_config.cache_clear()
    seed_admin(prod_env)
    client = _fresh_client(app)
    response = client.post(
        "/api/auth/login",
        json={"login": "admin", "password": "admin123"},
        headers={"Origin": "http://localhost:5173"},
    )
    assert response.status_code == 200


def test_mutation_without_origin_allowed(prod_env):
    """curl/мобильные клиенты не присылают Origin — не блокируются."""
    from app.api.main import app

    seed_admin(prod_env)
    client = _fresh_client(app)
    response = client.post(
        "/api/auth/login", json={"login": "admin", "password": "admin123"}
    )
    assert response.status_code == 200


def test_read_request_with_foreign_origin_allowed(prod_env):
    """Проверка Origin касается только мутаций: чтение с чужим Origin проходит."""
    from app.api.main import app

    client = _fresh_client(app)
    response = client.get(
        "/api/health", headers={"Origin": "https://evil.example"}
    )
    assert response.status_code == 200


def test_base_url_origin_allowed(prod_env, monkeypatch):
    """Origin публичного адреса (BASE_URL) разрешён для мутаций."""
    from app.api.main import app

    monkeypatch.setenv("BASE_URL", "https://sklad.example.com")
    get_config.cache_clear()
    seed_admin(prod_env)
    client = _fresh_client(app)
    response = client.post(
        "/api/auth/login",
        json={"login": "admin", "password": "admin123"},
        headers={"Origin": "https://sklad.example.com"},
    )
    assert response.status_code == 200


def test_mutation_with_origin_port_normalized(prod_env, monkeypatch):
    """Origin с портом против Host без порта (прокси нормализует Host) — проходит."""
    from app.api.main import app

    seed_admin(prod_env)
    client = _fresh_client(app)
    response = client.post(
        "/api/auth/login",
        json={"login": "admin", "password": "admin123"},
        headers={"Origin": "http://testserver:8080", "Host": "testserver"},
    )
    assert response.status_code == 200


# --------------------------------------------------------------------------- #
# Отключение доков (DOCS_ENABLED=0)
# --------------------------------------------------------------------------- #


def test_docs_available_by_default(client):
    assert client.get("/docs").status_code == 200
    assert client.get("/openapi.json").status_code == 200


def test_docs_disabled_in_production(prod_env, monkeypatch):
    from app.api.main import create_app

    monkeypatch.setenv("DOCS_ENABLED", "0")
    get_config.cache_clear()
    client = _fresh_client(create_app())

    assert client.get("/docs").status_code == 404
    assert client.get("/redoc").status_code == 404
    assert client.get("/openapi.json").status_code == 404
    # Сам API жив: health отвечает.
    assert client.get("/api/health").status_code == 200


# --------------------------------------------------------------------------- #
# CLI первого администратора (python -m app.bootstrap_admin)
# --------------------------------------------------------------------------- #


def test_create_admin_on_empty_storage(prod_env):
    from app.bootstrap_admin import create_admin
    from app.domain.passwords import verify_password

    login = create_admin("owner", "parol123")
    assert login == "owner"

    rows = read_sheet(prod_env, "Пользователи")
    header = rows[0]
    assert rows[1][header.index("Роль")] == "администратор"
    stored_hash = str(rows[1][header.index("Хеш_Пароля")])
    assert verify_password("parol123", stored_hash)


def test_create_admin_duplicate_login(prod_env):
    from app.bootstrap_admin import create_admin
    from app.domain.errors import ValidationError

    create_admin("owner", "parol123")
    with pytest.raises(ValidationError, match="уже занят"):
        create_admin("Owner", "другий123")


def test_create_admin_validates_input(prod_env):
    from app.bootstrap_admin import create_admin
    from app.domain.errors import ValidationError

    with pytest.raises(ValidationError):
        create_admin("ab", "parol123")
    with pytest.raises(ValidationError):
        create_admin("oklogin", "123")


def test_cli_main_creates_admin_and_returns_zero(prod_env, monkeypatch, capsys):
    import app.bootstrap_admin as cli

    passwords = iter(["parol123", "parol123"])
    monkeypatch.setattr(cli.getpass, "getpass", lambda _prompt="": next(passwords))
    monkeypatch.setattr("sys.argv", ["bootstrap_admin", "owner"])

    assert cli.main() == 0
    assert "создан" in capsys.readouterr().out
    rows = read_sheet(prod_env, "Пользователи")
    assert len(rows) == 2  # шапка + администратор


def test_cli_main_duplicate_returns_one(prod_env, monkeypatch, capsys):
    import app.bootstrap_admin as cli

    cli.create_admin("owner", "parol123")
    passwords = iter(["parol123", "parol123"])
    monkeypatch.setattr(cli.getpass, "getpass", lambda _prompt="": next(passwords))
    monkeypatch.setattr("sys.argv", ["bootstrap_admin", "owner"])

    assert cli.main() == 1
    assert "Ошибка" in capsys.readouterr().err


def test_cli_main_without_login_returns_one(monkeypatch, capsys):
    import app.bootstrap_admin as cli

    monkeypatch.setattr("sys.argv", ["bootstrap_admin"])
    assert cli.main() == 1
    assert "Использование" in capsys.readouterr().err
