import pytest

from guided_buzz.config import ConfigError, load_settings


@pytest.fixture
def key_file(tmp_path):
    path = tmp_path / "oauth-client.json"
    path.write_text('{"installed": {"client_secret": "SECRET-KEY-CONTENT"}}', encoding="utf-8")
    return path


def env(key_file, **overrides):
    base = {"GB_TEACHER_PASSWORD": "pw-123456", "GB_GOOGLE_OAUTH_CLIENT_FILE": str(key_file)}
    base.update(overrides)
    return {k: v for k, v in base.items() if v is not None}


def test_defaults(key_file):
    s = load_settings(env(key_file))
    assert s.host == "127.0.0.1"
    assert s.port == 8000
    assert s.max_questions == 500
    assert s.header_labels == ("題號", "題目", "作答")
    assert s.sheets_timeout_seconds == 10
    assert s.results_dir is None
    assert s.google_token_file == s.data_dir / "google-token.json"


def test_overrides(key_file, tmp_path):
    s = load_settings(
        env(
            key_file,
            GB_PORT="9000",
            GB_MAX_QUESTIONS="20",
            GB_HEADER_LABEL_ANSWER="答案",
            GB_DATA_DIR=str(tmp_path / "data"),
            GB_RESULTS_DIR=str(tmp_path / "results"),
            GB_GOOGLE_TOKEN_FILE=str(tmp_path / "tok.json"),
        )
    )
    assert s.google_token_file == tmp_path / "tok.json"
    assert s.port == 9000
    assert s.max_questions == 20
    assert s.header_labels[2] == "答案"
    assert s.data_dir == tmp_path / "data"
    assert s.results_dir == tmp_path / "results"


@pytest.mark.parametrize(
    "overrides, expected",
    [
        ({"GB_TEACHER_PASSWORD": None}, "GB_TEACHER_PASSWORD"),
        ({"GB_GOOGLE_OAUTH_CLIENT_FILE": None}, "GB_GOOGLE_OAUTH_CLIENT_FILE"),
        ({"GB_GOOGLE_OAUTH_CLIENT_FILE": "/no/such/client.json"}, "GB_GOOGLE_OAUTH_CLIENT_FILE"),
        ({"GB_MAX_QUESTIONS": "0"}, "GB_MAX_QUESTIONS"),
        ({"GB_PORT": "abc"}, "GB_PORT"),
        ({"GB_PORT": "70000"}, "GB_PORT"),
        ({"GB_HEADER_LABEL_NUMBER": "   "}, "GB_HEADER_LABEL_NUMBER"),
    ],
)
def test_invalid_values_fail_with_variable_name(key_file, overrides, expected):
    with pytest.raises(ConfigError) as exc:
        load_settings(env(key_file, **overrides))
    message = str(exc.value)
    assert expected in message
    assert "pw-123456" not in message
    assert "SECRET-KEY-CONTENT" not in message


def test_password_not_in_repr(key_file):
    assert "pw-123456" not in repr(load_settings(env(key_file)))
