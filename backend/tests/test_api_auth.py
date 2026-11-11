"""Тесты авторизации и разграничения прав.

Регистрация (bootstrap-администратор, роль «просмотр»), вход/выход, сессии,
401 для неавторизованных, 403 для роли «просмотр» при мутациях, управление
пользователями администратором и защита последнего администратора.
"""

from __future__ import annotations

import pytest

from conftest import make_new_workbook

from app.config import get_config


def _register(client, login="viewer1", password="parol123"):
    return client.post("/api/auth/register", json={"login": login, "password": password})


def _login(client, login, password):
    return client.post("/api/auth/login", json={"login": login, "password": password})


@pytest.fixture
def fresh_env(monkeypatch, tmp_path):
    """Чистое окружение без users-листов: для bootstrap-теста первой учётной записи."""
    import app.context as context

    data_file = tmp_path / "fresh.xlsx"
    monkeypatch.setenv("DATA_FILE", str(data_file))
    get_config.cache_clear()
    context._service = None
    context._auth_service = None
    yield data_file
    context._service = None
    context._auth_service = None
    get_config.cache_clear()


# --------------------------------------------------------------------------- #
# Регистрация и bootstrap-администратор
# --------------------------------------------------------------------------- #


def test_first_registered_user_becomes_admin(client):
    response = client.post(
        "/api/auth/register", json={"login": "first", "password": "parol123"}
    )
    # Первый пользователь уже зарегистрирован фикстурой client (admin),
    # поэтому здесь проверяем bootstrap отдельным клиентом ниже.


def test_bootstrap_first_account_is_admin_and_rest_are_viewers(fresh_env):
    from fastapi.testclient import TestClient
    from app.api.main import app

    client = TestClient(app)
    first = client.post(
        "/api/auth/register", json={"login": "owner", "password": "parol123"}
    )
    assert first.status_code == 201
    assert first.json()["role"] == "admin"
    assert first.json()["is_admin"] is True

    second = client.post(
        "/api/auth/register", json={"login": "guest", "password": "parol123"}
    )
    assert second.status_code == 201
    assert second.json()["role"] == "viewer"
    assert second.json()["is_admin"] is False


def test_register_duplicate_login_conflict(client):
    response = _register(client, login="admin")
    assert response.status_code == 409
    assert "уже занят" in response.json()["detail"]


@pytest.mark.parametrize(
    ("login", "password", "fragment"),
    [
        ("ab", "parol123", "от 3 до 32"),
        ("a" * 33, "parol123", "от 3 до 32"),
        ("bad login!", "parol123", "только буквы"),
        ("oklogin", "123", "от 6 до 128"),
        ("oklogin", "", "от 6 до 128"),
    ],
)
def test_register_validates_input(client, login, password, fragment):
    response = _register(client, login=login, password=password)
    assert response.status_code == 400
    assert fragment in response.json()["detail"]


# --------------------------------------------------------------------------- #
# Вход, выход, сессия
# --------------------------------------------------------------------------- #


def test_login_success_sets_session_and_me_works(client):
    response = _login(client, "admin", "admin123")
    assert response.status_code == 200
    assert response.json()["login"] == "admin"

    me = client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["login"] == "admin"
    assert me.json()["is_admin"] is True


def test_login_wrong_password_401_contract_text(client):
    response = _login(client, "admin", "wrong-password")
    assert response.status_code == 401
    assert response.json()["detail"] == "Неверный логин или пароль."


def test_login_unknown_user_same_contract_text(client):
    response = _login(client, "nosuchuser", "parol123")
    assert response.status_code == 401
    assert response.json()["detail"] == "Неверный логин или пароль."


def test_login_case_insensitive_login_name(client):
    response = _login(client, "ADMIN", "admin123")
    assert response.status_code == 200


def test_logout_deletes_session(client):
    assert _login(client, "admin", "admin123").status_code == 200
    assert client.get("/api/auth/me").status_code == 200

    response = client.post("/api/auth/logout")
    assert response.status_code == 204

    me = client.get("/api/auth/me")
    assert me.status_code == 401
    assert me.json()["detail"] == "Требуется вход в систему."


def test_blocked_user_cannot_login_and_session_dies(client):
    # Создаём и блокируем пользователя.
    created = client.post(
        "/api/users",
        json={"login": "blocked1", "password": "parol123", "role": "viewer"},
    )
    assert created.status_code == 201
    blocked = client.patch(
        f"/api/users/{created.json()['id']}", json={"blocked": True}
    )
    assert blocked.status_code == 200
    assert blocked.json()["blocked"] is True

    response = _login(client, "blocked1", "parol123")
    assert response.status_code == 401
    assert "заблокирована" in response.json()["detail"]

    # После разблокировки логин снова работает.
    unblocked = client.patch(
        f"/api/users/{created.json()['id']}", json={"blocked": False}
    )
    assert unblocked.status_code == 200
    assert _login(client, "blocked1", "parol123").status_code == 200


def test_me_without_session_returns_401(fresh_env):
    from fastapi.testclient import TestClient
    from app.api.main import app

    client = TestClient(app)
    response = client.get("/api/auth/me")
    assert response.status_code == 401


# --------------------------------------------------------------------------- #
# Неавторизованный доступ к данным склада закрыт
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "method,path",
    [
        ("get", "/api/stats"),
        ("get", "/api/locations"),
        ("get", "/api/boxes"),
        ("get", "/api/items"),
        ("get", "/api/search?q=отвёртка"),
        ("get", "/api/categories"),
        ("get", "/api/trash"),
        ("post", "/api/locations"),
        ("post", "/api/items"),
        ("post", "/api/backup"),
    ],
)
def test_warehouse_data_requires_login(data_file, method, path):
    from fastapi.testclient import TestClient
    from app.api.main import app

    make_new_workbook(data_file)
    client = TestClient(app)
    kwargs = {"json": {"name": "x"}} if method == "post" else {}
    response = getattr(client, method)(path, **kwargs)
    assert response.status_code == 401
    assert response.json()["detail"] == "Требуется вход в систему."


def test_health_stays_public(data_file):
    from fastapi.testclient import TestClient
    from app.api.main import app

    client = TestClient(app)
    assert client.get("/api/health").status_code == 200


# --------------------------------------------------------------------------- #
# Роль «просмотр»: только чтение
# --------------------------------------------------------------------------- #


def test_viewer_can_read_but_not_mutate(client, data_file):
    make_new_workbook(
        data_file,
        locations=[["loc1", "Гараж", "", "2026-01-01 10:00:00"]],
        boxes=[["box1", "Ящик А", "loc1", "", "2026-01-01 10:00:00"]],
        items=[["itm1", "Отвёртка", "box1", 3, "Инструменты", "", ""]],
    )
    assert _register(client, login="reader", password="parol123").status_code == 201

    # Чтение доступно.
    assert client.get("/api/items").status_code == 200
    assert client.get("/api/locations").status_code == 200
    assert client.get("/api/stats").status_code == 200

    # Любые мутации закрыты на сервере, даже при скрытом интерфейсе.
    forbidden = [
        ("post", "/api/items", {"name": "Молоток", "quantity": 1}),
        ("patch", "/api/items/itm1", {"name": "Хак"}),
        ("post", "/api/items/itm1/move", {"box_id": "box1"}),
        ("delete", "/api/items/itm1", None),
        ("delete", "/api/items?ids=itm1", None),
        ("put", "/api/items", {"items": []}),
        ("post", "/api/locations", {"name": "Сарай"}),
        ("post", "/api/boxes", {"name": "Ящик B"}),
        ("delete", "/api/locations/loc1", None),
        ("post", "/api/categories", {"name": "Хак"}),
        ("delete", "/api/trash", None),
        ("post", "/api/trash/item/itm1/restore", None),
        ("post", "/api/backup", None),
        ("post", "/api/cache/clear", None),
    ]
    for method, path, payload in forbidden:
        kwargs = {"json": payload} if payload is not None else {}
        response = getattr(client, method)(path, **kwargs)
        assert response.status_code == 403, f"{method} {path}: {response.text}"
        assert response.json()["detail"] == "Доступно только администратору."


# --------------------------------------------------------------------------- #
# Управление пользователями (только администратор)
# --------------------------------------------------------------------------- #


def test_users_endpoints_require_admin_role(client):
    assert _register(client, login="plain", password="parol123").status_code == 201

    # Сессия register — нового viewer'а: мутации и список пользователей закрыты.
    assert client.get("/api/users").status_code == 403
    assert client.post("/api/users", json={"login": "x1", "password": "parol123"}).status_code == 403


def test_admin_lists_creates_updates_and_deletes_users(client):
    created = client.post(
        "/api/users",
        json={"login": "manager", "password": "parol123", "role": "admin"},
    )
    assert created.status_code == 201
    manager = created.json()
    assert manager["role"] == "admin"
    assert "password" not in manager and "Хеш" not in str(manager)

    listed = client.get("/api/users")
    assert listed.status_code == 200
    logins = {user["login"] for user in listed.json()}
    assert {"admin", "manager"} <= logins

    renamed = client.patch(
        f"/api/users/{manager['id']}", json={"login": "manager2", "blocked": True}
    )
    assert renamed.status_code == 200
    assert renamed.json()["login"] == "manager2"
    assert renamed.json()["blocked"] is True

    deleted = client.delete(f"/api/users/{manager['id']}")
    assert deleted.status_code == 204
    remaining = {user["login"] for user in client.get("/api/users").json()}
    assert "manager2" not in remaining


def test_create_user_duplicate_login_409(client):
    response = client.post(
        "/api/users", json={"login": "Admin", "password": "parol123", "role": "viewer"}
    )
    assert response.status_code == 409
    assert "уже занят" in response.json()["detail"]


def test_create_user_unknown_role_400(client):
    response = client.post(
        "/api/users", json={"login": "who", "password": "parol123", "role": "root"}
    )
    assert response.status_code == 400
    assert "Неизвестная роль" in response.json()["detail"]


def test_admin_can_reset_password_and_new_password_works(client):
    created = client.post(
        "/api/users", json={"login": "temp", "password": "parol123", "role": "viewer"}
    ).json()

    updated = client.patch(f"/api/users/{created['id']}", json={"password": "новый123"})
    assert updated.status_code == 200

    fresh = client.post("/api/auth/logout")
    assert fresh.status_code == 204
    assert _login(client, "temp", "parol123").status_code == 401
    assert _login(client, "temp", "новый123").status_code == 200


def test_cannot_delete_last_admin(client):
    users = client.get("/api/users").json()
    admin = next(user for user in users if user["is_admin"])
    response = client.delete(f"/api/users/{admin['id']}")
    assert response.status_code == 400
    assert "последнего администратора" in response.json()["detail"]


def test_cannot_demote_last_admin(client):
    users = client.get("/api/users").json()
    admin = next(user for user in users if user["is_admin"])
    response = client.patch(f"/api/users/{admin['id']}", json={"role": "viewer"})
    assert response.status_code == 400

    # Но после создания второго администратора позволено.
    client.post(
        "/api/users", json={"login": "second", "password": "parol123", "role": "admin"}
    )
    response = client.patch(f"/api/users/{admin['id']}", json={"role": "viewer"})
    assert response.status_code == 200


def test_cannot_block_last_admin(client):
    users = client.get("/api/users").json()
    admin = next(user for user in users if user["is_admin"])
    response = client.patch(f"/api/users/{admin['id']}", json={"blocked": True})
    assert response.status_code == 400
    assert "последнего администратора" in response.json()["detail"]


def test_deleted_user_sessions_are_purged(client):
    created = client.post(
        "/api/users", json={"login": "short", "password": "parol123", "role": "viewer"}
    ).json()

    # Логин под пользователем (сессия в отдельном клиенте), затем удаление.
    from fastapi.testclient import TestClient

    other = TestClient(client.app)
    assert _login(other, "short", "parol123").status_code == 200
    assert other.get("/api/auth/me").status_code == 200

    assert client.delete(f"/api/users/{created['id']}").status_code == 204
    assert other.get("/api/auth/me").status_code == 401


def test_unknown_user_404(client):
    response = client.patch("/api/users/nosuchid", json={"blocked": True})
    assert response.status_code == 404
    assert "не найден" in response.json()["detail"]
