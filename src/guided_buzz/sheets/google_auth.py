"""Google OAuth 登入與 token 檔讀寫（research R13）。

老師執行 `uv run python -m guided_buzz login-google`，在瀏覽器以自己的 Google 帳號授權一次；
token 與帳號 email 存到 GB_GOOGLE_TOKEN_FILE（權限 600），伺服器啟動時再讀回。
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from google.auth import jwt
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",  # 只用來在錯誤訊息中顯示目前登入的帳號
]
LOGIN_COMMAND = "uv run python -m guided_buzz login-google"


class GoogleAuthError(Exception):
    """登入或讀取 token 失敗；訊息不含 token 內容。"""


def email_from_id_token(id_token: str | None) -> str:
    if not id_token:
        return ""
    # id token 剛從 Google 經由 TLS 取得，這裡只讀出 email 顯示用，不拿來做授權判斷
    return jwt.decode(id_token, verify=False).get("email", "")


def _default_flow(client_file: Path, scopes: list[str]):
    return InstalledAppFlow.from_client_secrets_file(str(client_file), scopes)


def login(client_file: Path, token_file: Path, flow_factory=_default_flow) -> str:
    try:
        flow = flow_factory(client_file, SCOPES)
    except (ValueError, KeyError, OSError):
        raise GoogleAuthError("OAuth client 設定檔無法讀取，請確認 GB_GOOGLE_OAUTH_CLIENT_FILE 指向「桌面應用程式」類型的 client JSON。") from None
    creds = flow.run_local_server(port=0, open_browser=True)
    email = email_from_id_token(getattr(creds, "id_token", None))
    data = json.loads(creds.to_json())
    data["account_email"] = email
    token_file.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(token_file, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(data, f)
    os.chmod(token_file, 0o600)  # 覆寫既有檔案時也確保權限
    return email


def load_credentials(token_file: Path) -> tuple[Credentials, str]:
    if not token_file.is_file():
        raise GoogleAuthError(f"尚未登入 Google，請先在終端機執行 `{LOGIN_COMMAND}`。")
    try:
        data = json.loads(token_file.read_text(encoding="utf-8"))
        creds = Credentials.from_authorized_user_info(data, SCOPES)
    except (ValueError, KeyError, TypeError):
        raise GoogleAuthError(f"Google token 檔格式不正確，請重新執行 `{LOGIN_COMMAND}`。") from None
    return creds, data.get("account_email", "")
