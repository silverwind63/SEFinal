"""完整流程後，log 中不得出現密碼、Token、金鑰內容與答案；原始碼與測試資料不得寫死機敏資料（Constitution 原則 III）。"""

import json
import logging
import re
from pathlib import Path

from tests.conftest import PASSWORD

ROOT = Path(__file__).resolve().parents[2]
SAMPLE_B = "1PXXwWiBKJNpPkLRoJLMzZWsAh4Jzn2bThHTeRAiq3Hg"
ACTIVITY = "11111111-1111-1111-1111-111111111111"
SECRET_ANSWER = "只屬於學生的答案-XYZ"


def test_full_flow_logs_no_secrets(client, sheets, settings, caplog):
    caplog.set_level(logging.DEBUG)
    settings.google_oauth_client_file.write_text('{"installed": {"client_secret": "KEY-CONTENT-123"}}', encoding="utf-8")
    token = client.post("/api/auth/teacher-login", json={"password": PASSWORD}).json()["token"]
    auth = {"Authorization": f"Bearer {token}"}
    sheets.add_fixture("sample_b")
    wid = client.post("/api/worksheets", json={"spreadsheet_url": SAMPLE_B}, headers=auth).json()["id"]
    client.post(f"/api/worksheets/{wid}/confirm", headers=auth)
    data = {
        "activity_id": ACTIVITY,
        "worksheet_id": wid,
        "owner": "teacher",
        "ended": True,
        "submissions": [{"question_nos": [6], "team_name": "第一組", "answers": {"6": SECRET_ANSWER}, "rank": 1, "outcome": "success"}],
    }
    (settings.results_dir / f"{ACTIVITY}.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    assert client.post(f"/api/worksheets/{wid}/writeback", json={"activity_id": ACTIVITY}, headers=auth).status_code == 200
    assert client.get(f"/api/activities/{ACTIVITY}/results.csv", headers=auth).status_code == 200
    for secret in (PASSWORD, token, "KEY-CONTENT-123", SECRET_ANSWER):
        assert secret not in caplog.text


def test_source_and_fixtures_have_no_hardcoded_secrets_or_paths():
    files = [p for d in ("src", "tests/fixtures") for p in (ROOT / d).rglob("*") if p.is_file() and p.suffix in {".py", ".json", ".js", ".html"}]
    assert files
    for path in files:
        text = path.read_text(encoding="utf-8")
        assert not re.search(r"(/Users/|/home/|[A-Z]:\\\\)", text), path
        assert "private_key" not in text and "PRIVATE KEY" not in text, path
        assert not re.search(r'"(refresh_token|client_secret)"\s*:\s*"[^"]+"', text), path
        assert not re.search(r"(?i)password\s*=\s*['\"][^'\"]+['\"]", text), path


def test_buzz_activity_logs_no_codes_tokens_or_answers(client, sheets, caplog):
    """完成一場搶答活動後，log 中不含組別代碼、學生 Token、老師 Token 與答案（002 tasks T061）。"""
    from tests.buzz import started, submit

    caplog.set_level(logging.DEBUG)
    token = client.post("/api/auth/teacher-login", json={"password": PASSWORD}).json()["token"]
    auth = {"Authorization": f"Bearer {token}"}
    activity, students = started(client, auth, sheets)
    aid = activity["id"]
    with client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "auth", "token": students[0]["Authorization"].split()[1]})
        ws.receive_json()
    submit(client, students[0], "Q6", {6: SECRET_ANSWER})
    submit(client, students[1], "Q6", {6: SECRET_ANSWER + "2"})
    client.post("/api/join", json={"code": "ZZZZZZ"}, headers={"X-Window-Id": "w"})
    client.post(f"/api/activities/{aid}/teams/2/regenerate-code", headers=auth)
    client.post(f"/api/activities/{aid}/units/Q6/invalidate", headers=auth)
    client.post(f"/api/activities/{aid}/end", headers=auth)
    secrets = [token, SECRET_ANSWER, *(t["code"] for t in activity["teams"]), *(s["Authorization"].split()[1] for s in students)]
    for secret in secrets:
        assert secret not in caplog.text
    assert "已結束" in caplog.text  # 確認 log 確實有被收集
