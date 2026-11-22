import logging

from tests.conftest import PASSWORD


def test_login_returns_token(client):
    res = client.post("/api/auth/teacher-login", json={"password": PASSWORD})
    assert res.status_code == 200
    body = res.json()
    assert body["token"] and body["expires_in"] == 60


def test_wrong_password(client):
    res = client.post("/api/auth/teacher-login", json={"password": "wrong"})
    assert res.status_code == 401
    assert res.json()["error"]["code"] == "INVALID_CREDENTIALS"


def test_missing_password_field(client):
    res = client.post("/api/auth/teacher-login", json={})
    assert res.status_code == 422
    assert res.json()["error"]["code"] == "VALIDATION_ERROR"


def test_lockout_after_repeated_failures(client):
    for _ in range(3):
        client.post("/api/auth/teacher-login", json={"password": "wrong"})
    res = client.post("/api/auth/teacher-login", json={"password": PASSWORD})
    assert res.status_code == 429
    assert res.json()["error"]["code"] == "LOGIN_LOCKED"
    assert "秒" in res.json()["error"]["message"]


def test_protected_endpoint_requires_token(client):
    assert client.get("/api/auth/session").status_code == 401
    res = client.get("/api/auth/session", headers={"Authorization": "Bearer nope"})
    assert res.status_code == 401
    assert res.json()["error"]["code"] == "UNAUTHORIZED"


def test_expired_token(client, settings, monkeypatch):
    token = client.post("/api/auth/teacher-login", json={"password": PASSWORD}).json()["token"]
    import guided_buzz.auth.teacher as teacher

    now = teacher.time.monotonic()
    monkeypatch.setattr(teacher.time, "monotonic", lambda: now + 61)
    assert client.get("/api/auth/session", headers={"Authorization": f"Bearer {token}"}).status_code == 401


def test_logs_do_not_contain_secrets(client, caplog):
    caplog.set_level(logging.DEBUG)
    token = client.post("/api/auth/teacher-login", json={"password": PASSWORD}).json()["token"]
    client.post("/api/auth/teacher-login", json={"password": "wrong-guess"})
    assert PASSWORD not in caplog.text and token not in caplog.text and "wrong-guess" not in caplog.text
