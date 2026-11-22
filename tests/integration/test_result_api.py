import json

from guided_buzz.domain.errors import SheetForbidden, SheetsUnavailable

SAMPLE_B = "1PXXwWiBKJNpPkLRoJLMzZWsAh4Jzn2bThHTeRAiq3Hg"
ACTIVITY = "11111111-1111-1111-1111-111111111111"
SUBMISSIONS = [
    {"question_nos": [1, 2], "team_name": "第一組", "answers": {"1": "CPU", "2": "作業系統"}, "rank": 1, "outcome": "success"},
    {"question_nos": [5], "team_name": "第二組", "answers": {"5": "1"}, "rank": 1, "outcome": "invalidated"},
    {"question_nos": [5], "team_name": "第三組", "answers": {"5": "0"}, "rank": 2, "outcome": "success"},
]


def confirmed_b(client, auth, sheets):
    sheets.add_fixture("sample_b")
    wid = client.post("/api/worksheets", json={"spreadsheet_url": SAMPLE_B}, headers=auth).json()["id"]
    client.post(f"/api/worksheets/{wid}/confirm", headers=auth)
    return wid


def write_result(settings, worksheet_id, ended=True, submissions=SUBMISSIONS, activity=ACTIVITY):
    data = {"activity_id": activity, "worksheet_id": worksheet_id, "owner": "teacher", "ended": ended, "submissions": submissions}
    (settings.results_dir / f"{activity}.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def writeback(client, auth, wid, activity=ACTIVITY):
    return client.post(f"/api/worksheets/{wid}/writeback", json={"activity_id": activity}, headers=auth)


def test_writeback_writes_only_target_cells(client, auth, sheets, settings):
    wid = confirmed_b(client, auth, sheets)
    write_result(settings, wid)
    res = writeback(client, auth, wid)
    assert res.status_code == 200
    assert res.json() == {"filled": [1, 2, 5], "unfilled": [3, 4, 6], "skipped_non_empty": []}
    assert len(sheets.writes) == 1
    _, written = sheets.writes[0]
    assert {r.cell: t for r, t in written.items()} == {"H5": "CPU", "H6": "作業系統", "G11": "0"}


def test_existing_content_not_overwritten(client, auth, sheets, settings):
    wid = confirmed_b(client, auth, sheets)
    write_result(settings, wid)
    sheets.set_cell(SAMPLE_B, "學習單", "H5", "老師的筆記")
    body = writeback(client, auth, wid).json()
    assert body["skipped_non_empty"] == [1] and body["filled"] == [2, 5]
    assert sheets.sheets[SAMPLE_B].sheets[0].values["H5"] == "老師的筆記"


def test_activity_not_ended(client, auth, sheets, settings):
    wid = confirmed_b(client, auth, sheets)
    write_result(settings, wid, ended=False)
    res = writeback(client, auth, wid)
    assert res.status_code == 409 and res.json()["error"]["code"] == "INVALID_STATE"


def test_worksheet_not_confirmed(client, auth, sheets, settings):
    sheets.add_fixture("sample_b")
    wid = client.post("/api/worksheets", json={"spreadsheet_url": SAMPLE_B}, headers=auth).json()["id"]
    write_result(settings, wid)
    assert writeback(client, auth, wid).status_code == 409


def test_structure_changed_blocks_writes(client, auth, sheets, settings):
    from tests import factories as f

    wid = confirmed_b(client, auth, sheets)
    write_result(settings, wid)
    sheets.add(f.grid(f.standard_sheet(6, gap=False), spreadsheet_id=SAMPLE_B, title="範例 B"))
    res = writeback(client, auth, wid)
    assert res.status_code == 409 and res.json()["error"]["code"] == "STRUCTURE_CHANGED"
    assert sheets.writes == []


def test_write_errors(client, auth, sheets, settings):
    wid = confirmed_b(client, auth, sheets)
    write_result(settings, wid)
    sheets.write_errors[SAMPLE_B] = SheetForbidden(sheets.service_account_email)
    assert writeback(client, auth, wid).status_code == 403
    sheets.write_errors[SAMPLE_B] = SheetsUnavailable()
    assert writeback(client, auth, wid).status_code == 503


def test_activity_for_other_worksheet(client, auth, sheets, settings):
    wid = confirmed_b(client, auth, sheets)
    write_result(settings, "33333333-3333-3333-3333-333333333333")
    res = writeback(client, auth, wid)
    assert res.status_code == 404 and res.json()["error"]["code"] == "NOT_FOUND"


def test_writeback_requires_token(client, auth, sheets, settings):
    wid = confirmed_b(client, auth, sheets)
    write_result(settings, wid)
    assert client.post(f"/api/worksheets/{wid}/writeback", json={"activity_id": ACTIVITY}).status_code == 401
    assert sheets.writes == []


def test_csv_export(client, auth, sheets, settings):
    wid = confirmed_b(client, auth, sheets)
    write_result(settings, wid)
    res = client.get(f"/api/activities/{ACTIVITY}/results.csv", headers=auth)
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("text/csv")
    assert res.headers["x-record-count"] == "4"
    assert res.content.startswith("﻿題號".encode())


def test_csv_empty_activity(client, auth, sheets, settings):
    wid = confirmed_b(client, auth, sheets)
    write_result(settings, wid, submissions=[])
    res = client.get(f"/api/activities/{ACTIVITY}/results.csv", headers=auth)
    assert res.status_code == 200 and res.headers["x-record-count"] == "0"


def test_csv_errors(client, auth, sheets, settings):
    wid = confirmed_b(client, auth, sheets)
    write_result(settings, wid, ended=False)
    assert client.get(f"/api/activities/{ACTIVITY}/results.csv", headers=auth).status_code == 409
    assert client.get("/api/activities/99999999-9999-9999-9999-999999999999/results.csv", headers=auth).status_code == 404
    assert client.get(f"/api/activities/{ACTIVITY}/results.csv").status_code == 401
