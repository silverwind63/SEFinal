import base64
import json
import stat

import pytest

from guided_buzz.sheets.google_auth import SCOPES, GoogleAuthError, email_from_id_token, load_credentials, login


def fake_id_token(payload: dict) -> str:
    part = lambda d: base64.urlsafe_b64encode(json.dumps(d).encode()).rstrip(b"=").decode()
    return f"{part({'alg': 'RS256', 'typ': 'JWT'})}.{part(payload)}.{base64.urlsafe_b64encode(b'sig').rstrip(b'=').decode()}"


class FakeCredentials:
    def __init__(self):
        self.id_token = fake_id_token({"email": "teacher@example.com"})

    def to_json(self):
        return json.dumps(
            {"token": "access-123", "refresh_token": "refresh-456", "client_id": "cid", "client_secret": "csecret", "token_uri": "https://oauth2.googleapis.com/token", "scopes": SCOPES}
        )


class FakeFlow:
    def __init__(self):
        self.called = False

    def run_local_server(self, **kwargs):
        self.called = True
        return FakeCredentials()


def test_login_saves_token_with_private_permissions(tmp_path):
    token_file = tmp_path / "nested" / "google-token.json"
    flow = FakeFlow()
    email = login(tmp_path / "client.json", token_file, flow_factory=lambda client_file, scopes: flow)
    assert flow.called and email == "teacher@example.com"
    assert stat.S_IMODE(token_file.stat().st_mode) == 0o600
    data = json.loads(token_file.read_text(encoding="utf-8"))
    assert data["account_email"] == "teacher@example.com" and data["refresh_token"] == "refresh-456"


def test_load_credentials_round_trip(tmp_path):
    token_file = tmp_path / "google-token.json"
    login(tmp_path / "client.json", token_file, flow_factory=lambda c, s: FakeFlow())
    creds, email = load_credentials(token_file)
    assert email == "teacher@example.com"
    assert creds.refresh_token == "refresh-456"


def test_missing_token_file_explains_login_command(tmp_path):
    with pytest.raises(GoogleAuthError) as exc:
        load_credentials(tmp_path / "none.json")
    assert "login-google" in str(exc.value)


@pytest.mark.parametrize("content", ["not json", '{"token": "x"}'])
def test_broken_token_file(tmp_path, content):
    token_file = tmp_path / "google-token.json"
    token_file.write_text(content, encoding="utf-8")
    with pytest.raises(GoogleAuthError) as exc:
        load_credentials(token_file)
    assert "login-google" in str(exc.value) and content not in str(exc.value)


def test_email_from_id_token():
    assert email_from_id_token(fake_id_token({"email": "a@b.c"})) == "a@b.c"
    assert email_from_id_token(None) == ""
