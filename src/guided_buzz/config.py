"""讀取並驗證 GB_* 環境變數（research R10）。缺少必要值或值不合法時拒絕啟動。"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv


class ConfigError(Exception):
    """設定錯誤；訊息只含變數名稱與原因，不含機敏值。"""


@dataclass(frozen=True)
class Settings:
    teacher_password: str = field(repr=False)
    google_oauth_client_file: Path
    google_token_file: Path
    data_dir: Path
    host: str
    port: int
    sheets_timeout_seconds: float
    max_questions: int
    header_labels: tuple[str, str, str]  # 題號、題目、作答
    token_ttl_seconds: int
    login_max_failures: int
    login_lock_seconds: int
    results_dir: Path | None
    # 002 搶答活動（research R10）
    max_teams: int
    team_name_max: int
    max_answer_length: int
    fairness_enabled: bool
    cooldown_seconds: int
    cooldown_lead: int
    join_max_failures: int
    join_lock_seconds: int
    join_global_failures_per_min: int
    ws_auth_timeout_seconds: float


def load_settings(env: Mapping[str, str] | None = None) -> Settings:
    if env is None:
        load_dotenv(override=False)
        env = os.environ
    problems: list[str] = []

    def text(name: str, default: str | None = None, required: bool = False) -> str:
        value = env.get(name, default)
        if value is None or not value.strip():
            if required or default is not None:
                problems.append(f"{name} 未設定或為空白")
            return ""
        return value.strip()

    def number(name: str, default: str, cast=int, low=1, high=None):
        raw = env.get(name, default)
        try:
            value = cast(raw)
        except ValueError:
            problems.append(f"{name} 必須是數字")
            return cast(default)
        if value < low or (high is not None and value > high):
            limit = f"{low}–{high}" if high is not None else f"至少 {low}"
            problems.append(f"{name} 超出範圍（{limit}）")
        return value

    def flag(name: str, default: str) -> bool:
        raw = env.get(name, default).strip().lower()
        if raw in ("true", "1", "yes", "on"):
            return True
        if raw in ("false", "0", "no", "off"):
            return False
        problems.append(f"{name} 必須是 true 或 false")
        return default == "true"

    password = text("GB_TEACHER_PASSWORD", required=True)
    client_file = text("GB_GOOGLE_OAUTH_CLIENT_FILE", required=True)
    if client_file and not Path(client_file).is_file():
        problems.append("GB_GOOGLE_OAUTH_CLIENT_FILE 指向的 OAuth client 設定檔不存在")
    data_dir = Path(text("GB_DATA_DIR", "./var"))
    token_file = env.get("GB_GOOGLE_TOKEN_FILE", "").strip()
    labels = (
        text("GB_HEADER_LABEL_NUMBER", "題號"),
        text("GB_HEADER_LABEL_QUESTION", "題目"),
        text("GB_HEADER_LABEL_ANSWER", "作答"),
    )
    results_dir = env.get("GB_RESULTS_DIR", "").strip()
    settings = Settings(
        teacher_password=password,
        google_oauth_client_file=Path(client_file),
        google_token_file=Path(token_file) if token_file else data_dir / "google-token.json",
        data_dir=data_dir,
        host=text("GB_HOST", "127.0.0.1"),
        port=number("GB_PORT", "8000", high=65535),
        sheets_timeout_seconds=number("GB_SHEETS_TIMEOUT_SECONDS", "10", cast=float),
        max_questions=number("GB_MAX_QUESTIONS", "500"),
        header_labels=labels,
        token_ttl_seconds=number("GB_TOKEN_TTL_SECONDS", "28800"),
        login_max_failures=number("GB_LOGIN_MAX_FAILURES", "5"),
        login_lock_seconds=number("GB_LOGIN_LOCK_SECONDS", "300"),
        results_dir=Path(results_dir) if results_dir else None,
        max_teams=number("GB_MAX_TEAMS", "20"),
        team_name_max=number("GB_TEAM_NAME_MAX", "20"),
        max_answer_length=number("GB_MAX_ANSWER_LENGTH", "200"),
        fairness_enabled=flag("GB_FAIRNESS_ENABLED", "true"),
        cooldown_seconds=number("GB_COOLDOWN_SECONDS", "10", high=600),
        cooldown_lead=number("GB_COOLDOWN_LEAD", "2", high=100),
        join_max_failures=number("GB_JOIN_MAX_FAILURES", "5"),
        join_lock_seconds=number("GB_JOIN_LOCK_SECONDS", "60"),
        join_global_failures_per_min=number("GB_JOIN_GLOBAL_FAILURES_PER_MIN", "60"),
        ws_auth_timeout_seconds=number("GB_WS_AUTH_TIMEOUT_SECONDS", "5", cast=float, low=0.1, high=60),
    )
    if problems:
        raise ConfigError("設定錯誤，伺服器無法啟動：\n- " + "\n- ".join(problems))
    return settings
