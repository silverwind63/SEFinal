import json
import socket
from pathlib import Path

import httplib2
import pytest
from googleapiclient.errors import HttpError

import google.auth.exceptions

from guided_buzz.domain.errors import GoogleAuthExpired, SheetForbidden, SheetNotFound, SheetsUnavailable
from guided_buzz.domain.models import CellRef
from guided_buzz.sheets.google_gateway import GoogleSheetsGateway, a1_range, grid_from_response

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "sheets"
EMAIL = "teacher@example.com"


def load(name):
    return json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))


class FakeRequest:
    def __init__(self, result=None, error=None):
        self.result, self.error = result, error

    def execute(self):
        if self.error:
            raise self.error
        return self.result


class FakeService:
    """模擬 googleapiclient 的 service 物件：spreadsheets().get / values().batchUpdate。"""

    def __init__(self, result=None, error=None):
        self.result, self.error, self.calls = result, error, []

    def spreadsheets(self):
        return self

    def values(self):
        return self

    def get(self, **kwargs):
        self.calls.append(("get", kwargs))
        return FakeRequest(self.result, self.error)

    def batchUpdate(self, **kwargs):
        self.calls.append(("batchUpdate", kwargs))
        return FakeRequest({}, self.error)


def http_error(status):
    return HttpError(httplib2.Response({"status": status}), b'{"error": {"message": "raw google text"}}')


def gateway(service):
    return GoogleSheetsGateway(service=service, account_email=EMAIL)


def test_sample_b_converts_values_and_merges():
    grid = grid_from_response(load("sample_b"))
    sheet = grid.sheets[0]
    assert grid.spreadsheet_id == "1PXXwWiBKJNpPkLRoJLMzZWsAh4Jzn2bThHTeRAiq3Hg"
    assert (sheet.sheet_id, sheet.title) == (0, "學習單")
    assert sheet.values["B4"] == "題號"
    assert sheet.values["G5"] == "（1）"
    assert "H5" not in sheet.values
    assert {"B5:B6", "B8:B9", "G11:H11", "C4:F4"} <= set(sheet.merges)


def test_sample_a_has_six_answer_merges():
    sheet = grid_from_response(load("sample_a")).sheets[0]
    assert [m for m in sheet.merges if m.startswith("G") and m != "G4:H4"] == [f"G{r}:H{r}" for r in range(5, 16, 2)]


def test_fetch_requests_only_needed_fields():
    service = FakeService(result=load("sample_a"))
    gateway(service).fetch_grid("sid")
    _, kwargs = service.calls[0]
    assert kwargs["includeGridData"] is True and "merges" in kwargs["fields"]


@pytest.mark.parametrize(
    "error, expected",
    [
        (http_error(403), SheetForbidden),
        (http_error(404), SheetNotFound),
        (http_error(401), GoogleAuthExpired),
        (google.auth.exceptions.RefreshError("invalid_grant"), GoogleAuthExpired),
        (http_error(500), SheetsUnavailable),
        (socket.timeout(), SheetsUnavailable),
        (ConnectionError(), SheetsUnavailable),
    ],
)
def test_errors_are_mapped(error, expected):
    with pytest.raises(expected) as exc:
        gateway(FakeService(error=error)).fetch_grid("sid")
    assert "raw google text" not in exc.value.message


def test_forbidden_message_names_logged_in_account():
    with pytest.raises(SheetForbidden) as exc:
        gateway(FakeService(error=http_error(403))).fetch_grid("sid")
    assert EMAIL in exc.value.message


def test_write_uses_raw_and_escaped_ranges():
    service = FakeService()
    gateway(service).write_cells("sid", {CellRef(3, "Bob's 學習單", "H5"): "=1+1"})
    _, kwargs = service.calls[0]
    assert kwargs["body"]["valueInputOption"] == "RAW"
    assert kwargs["body"]["data"] == [{"range": "'Bob''s 學習單'!H5", "values": [["=1+1"]]}]


def test_write_nothing_makes_no_call():
    service = FakeService()
    gateway(service).write_cells("sid", {})
    assert service.calls == []


def test_a1_range_with_spaces():
    assert a1_range(CellRef(0, "Sheet 1", "A1")) == "'Sheet 1'!A1"


def test_auth_expired_message_tells_how_to_log_in_again():
    with pytest.raises(GoogleAuthExpired) as exc:
        gateway(FakeService(error=google.auth.exceptions.RefreshError("invalid_grant"))).fetch_grid("sid")
    assert "login-google" in exc.value.message and "invalid_grant" not in exc.value.message
