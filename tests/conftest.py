import pytest
from fastapi.testclient import TestClient

from guided_buzz.api.app import create_app
from guided_buzz.config import load_settings
from tests.fakes import FakeSheetsGateway

PASSWORD = "test-password-123"


@pytest.fixture
def settings(tmp_path):
    key = tmp_path / "fake-key.json"
    key.write_text("{}", encoding="utf-8")
    results = tmp_path / "results"
    results.mkdir()
    return load_settings(
        {
            "GB_TEACHER_PASSWORD": PASSWORD,
            "GB_GOOGLE_CREDENTIALS_FILE": str(key),
            "GB_DATA_DIR": str(tmp_path / "data"),
            "GB_RESULTS_DIR": str(results),
            "GB_LOGIN_MAX_FAILURES": "3",
            "GB_TOKEN_TTL_SECONDS": "60",
        }
    )


@pytest.fixture
def sheets():
    return FakeSheetsGateway()


@pytest.fixture
def client(settings, sheets):
    with TestClient(create_app(settings, sheets)) as c:
        yield c


@pytest.fixture
def token(client):
    return client.post("/api/auth/teacher-login", json={"password": PASSWORD}).json()["token"]


@pytest.fixture
def auth(token):
    return {"Authorization": f"Bearer {token}"}
