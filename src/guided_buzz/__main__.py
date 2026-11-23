"""啟動伺服器：uv run python -m guided_buzz
登入 Google：uv run python -m guided_buzz login-google
"""

import sys

import uvicorn

from guided_buzz.api.app import create_app
from guided_buzz.config import ConfigError, load_settings
from guided_buzz.sheets.google_auth import GoogleAuthError, load_credentials, login
from guided_buzz.sheets.google_gateway import GoogleSheetsGateway

USAGE = "用法：python -m guided_buzz [login-google]"


def main() -> None:
    args = sys.argv[1:]
    if args not in ([], ["login-google"]):
        sys.exit(USAGE)
    try:
        settings = load_settings()
    except ConfigError as e:
        sys.exit(str(e))
    try:
        if args == ["login-google"]:
            email = login(settings.google_oauth_client_file, settings.google_token_file)
            print(f"已登入 Google 帳號：{email}\ntoken 已存到 {settings.google_token_file}（請勿提交到版本庫）")
            return
        creds, email = load_credentials(settings.google_token_file)
    except GoogleAuthError as e:
        sys.exit(str(e))
    gateway = GoogleSheetsGateway(creds, settings.sheets_timeout_seconds, account_email=email)
    # 搶答活動的狀態與判定鎖都在記憶體中（002 research R1），只能有一個程序，因此固定 workers=1。
    uvicorn.run(create_app(settings, gateway), host=settings.host, port=settings.port, workers=1)


if __name__ == "__main__":
    main()
