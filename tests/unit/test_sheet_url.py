import pytest

from guided_buzz.domain.errors import ImportErrorCode, ImportFailed
from guided_buzz.sheets.url import parse_spreadsheet_id

SID = "1PXXwWiBKJNpPkLRoJLMzZWsAh4Jzn2bThHTeRAiq3Hg"


@pytest.mark.parametrize(
    "text",
    [
        f"https://docs.google.com/spreadsheets/d/{SID}/edit?usp=sharing",
        f"https://docs.google.com/spreadsheets/d/{SID}/edit#gid=0",
        f"https://docs.google.com/spreadsheets/d/{SID}",
        f"  {SID}  ",
    ],
)
def test_accepts_urls_and_ids(text):
    assert parse_spreadsheet_id(text) == SID


@pytest.mark.parametrize(
    "text",
    [
        "",
        "https://example.com/spreadsheets/d/" + SID,
        "https://docs.google.com/spreadsheets/d/",
        "abc123",
        SID[:-5] + "!@#$%",
        "https://docs.google.com/spreadsheets/d/" + "a" * 2048,
    ],
)
def test_rejects_invalid(text):
    with pytest.raises(ImportFailed) as exc:
        parse_spreadsheet_id(text)
    assert exc.value.issues[0].code is ImportErrorCode.INVALID_SHEET_URL
    assert "網址格式不正確" in exc.value.issues[0].message
