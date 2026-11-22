from guided_buzz.domain.errors import SheetForbidden, SheetsUnavailable

SAMPLE_B = "1PXXwWiBKJNpPkLRoJLMzZWsAh4Jzn2bThHTeRAiq3Hg"
URL_B = f"https://docs.google.com/spreadsheets/d/{SAMPLE_B}/edit?usp=sharing"


def import_b(client, auth, sheets):
    sheets.add_fixture("sample_b")
    return client.post("/api/worksheets", json={"spreadsheet_url": URL_B}, headers=auth)


def test_import_preview_without_question_text(client, auth, sheets):
    res = import_b(client, auth, sheets)
    assert res.status_code == 201
    body = res.json()
    assert body["status"] == "pending" and body["spreadsheet_title"] == sheets.sheets[SAMPLE_B].title
    assert (body["question_count"], body["group_count"]) == (6, 2)
    assert body["questions"][0] == {"question_no": 1, "sheet": "學習單", "cell": "H5", "source_label": "1", "sub_label": "（1）", "group_no": 1}
    assert body["groups"][1] == {"group_no": 2, "source_label": "2", "question_nos": [3, 4]}
    texts = sheets.question_texts(SAMPLE_B)
    assert len(texts) == 6
    assert not any(t in res.text for t in texts)


def test_confirm_and_state_rules(client, auth, sheets):
    wid = import_b(client, auth, sheets).json()["id"]
    assert client.post(f"/api/worksheets/{wid}/confirm", headers=auth).json()["status"] == "confirmed"
    again = client.post(f"/api/worksheets/{wid}/confirm", headers=auth)
    assert again.status_code == 409 and again.json()["error"]["code"] == "INVALID_STATE"
    assert client.get(f"/api/worksheets/{wid}", headers=auth).json()["status"] == "confirmed"


def test_cancel_then_confirm_conflicts(client, auth, sheets):
    wid = import_b(client, auth, sheets).json()["id"]
    assert client.post(f"/api/worksheets/{wid}/cancel", headers=auth).json() == {"id": wid, "status": "cancelled"}
    assert client.post(f"/api/worksheets/{wid}/confirm", headers=auth).status_code == 409


def test_invalid_url(client, auth):
    res = client.post("/api/worksheets", json={"spreadsheet_url": "https://example.com/x"}, headers=auth)
    assert res.status_code == 422 and res.json()["error"]["code"] == "INVALID_SHEET_URL"


def test_forbidden_names_logged_in_account(client, auth, sheets):
    sheets.fetch_errors[SAMPLE_B] = SheetForbidden(sheets.account_email)
    res = client.post("/api/worksheets", json={"spreadsheet_url": URL_B}, headers=auth)
    assert res.status_code == 403 and res.json()["error"]["code"] == "SHEET_FORBIDDEN"
    assert sheets.account_email in res.json()["error"]["message"]


def test_not_found_and_unavailable(client, auth, sheets):
    res = client.post("/api/worksheets", json={"spreadsheet_url": URL_B}, headers=auth)
    assert res.status_code == 404 and res.json()["error"]["code"] == "SHEET_NOT_FOUND"
    sheets.fetch_errors[SAMPLE_B] = SheetsUnavailable()
    res = client.post("/api/worksheets", json={"spreadsheet_url": URL_B}, headers=auth)
    assert res.status_code == 503 and res.json()["error"]["code"] == "SHEETS_UNAVAILABLE"


def test_parse_errors_listed_with_location(client, auth, sheets):
    from tests import factories as f

    sheets.add(f.grid(f.standard_sheet(3, prefilled={2: "x"}), spreadsheet_id=SAMPLE_B))
    res = client.post("/api/worksheets", json={"spreadsheet_url": SAMPLE_B}, headers=auth)
    assert res.status_code == 422
    issue = res.json()["error"]["issues"][0]
    assert issue["code"] == "NO_BLANK_IN_ROW" and issue["row"] == f.row_of(2)


def test_requires_token(client, sheets):
    sheets.add_fixture("sample_b")
    assert client.post("/api/worksheets", json={"spreadsheet_url": URL_B}).status_code == 401


def test_unknown_id(client, auth):
    assert client.get("/api/worksheets/00000000-0000-0000-0000-000000000000", headers=auth).status_code == 404
    assert client.post("/api/worksheets/not-a-uuid/confirm", headers=auth).status_code == 404


def test_list_only_own(client, auth, sheets):
    wid = import_b(client, auth, sheets).json()["id"]
    items = client.get("/api/worksheets", headers=auth).json()
    assert [i["id"] for i in items] == [wid]
    assert set(items[0]) == {"id", "spreadsheet_title", "status", "question_count", "group_count", "created_at"}
