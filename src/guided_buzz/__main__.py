"""啟動伺服器：uv run python -m guided_buzz"""

import sys

import uvicorn

from guided_buzz.api.app import create_app
from guided_buzz.config import ConfigError, load_settings
from guided_buzz.sheets.google_gateway import GoogleSheetsGateway


def main() -> None:
    try:
        settings = load_settings()
    except ConfigError as e:
        sys.exit(str(e))
    try:
        gateway = GoogleSheetsGateway(settings.google_credentials_file, settings.sheets_timeout_seconds)
    except (ValueError, KeyError, OSError):
        sys.exit("設定錯誤，伺服器無法啟動：\n- GB_GOOGLE_CREDENTIALS_FILE 不是有效的 service account 金鑰檔")
    uvicorn.run(create_app(settings, gateway), host=settings.host, port=settings.port)


if __name__ == "__main__":
    main()
