"""學生端 API：加入（T019）、送出（T033）。"""

import pytest

from tests.buzz import create_activity, join, started, student_auth, submit


def test_join_with_correct_code(client, auth, sheets):
    activity = create_activity(client, auth, sheets)
    res = join(client, activity["teams"][1]["code"].lower())  # 不分大小寫
    body = res.json()
    assert res.status_code == 200
    assert body["team"] == {"id": 2, "name": "第二組"} and body["phase"] == "preparing" and body["token"]


def test_wrong_code_reveals_nothing(client, auth, sheets):
    create_activity(client, auth, sheets)
    res = join(client, "ZZZZZZ")
    assert res.status_code == 401
    assert res.json()["error"]["code"] == "INVALID_CODE"
    assert "組" not in res.json()["error"]["message"].replace("組別代碼", "")


def test_malformed_code_422(client, auth, sheets):
    create_activity(client, auth, sheets)
    assert join(client, "AB").status_code == 422


def test_window_locked_after_five_failures_other_window_ok(client, auth, sheets):
    activity = create_activity(client, auth, sheets)
    for _ in range(5):
        assert join(client, "ZZZZZZ", window="bad").status_code == 401
    locked = join(client, activity["teams"][0]["code"], window="bad")
    assert locked.status_code == 429 and locked.json()["error"]["retry_after_seconds"] > 0
    assert join(client, activity["teams"][0]["code"], window="good").status_code == 200


def test_multiple_windows_join_same_team(client, auth, sheets):
    activity = create_activity(client, auth, sheets)
    code = activity["teams"][0]["code"]
    a, b = student_auth(client, code, "w1"), student_auth(client, code, "w2")
    assert a != b
    assert client.get("/api/me", headers=a).json()["team"]["id"] == 1
    assert client.get("/api/me", headers=b).json()["team"]["id"] == 1


def test_join_without_live_activity(client):
    assert join(client, "ABCDEF").status_code == 401


def test_submit_success_and_not_won_messages(client, auth, sheets):
    _, students = started(client, auth, sheets)
    r1 = submit(client, students[0], "G1", {1: "CPU", 2: "作業系統"})
    r2 = submit(client, students[1], "G1", {1: "x", 2: "y"})
    assert r1.json() == {"unit_key": "G1", "rank": 1, "outcome": "success", "message": "搶答成功！"}
    assert r2.json()["message"] == "未搶到，第 2 順位"


@pytest.mark.parametrize("extra", [{"client_time": "2026-01-01T00:00:00Z"}, {"outcome": "success"}])
def test_client_supplied_fields_rejected(client, auth, sheets, extra):
    _, students = started(client, auth, sheets)
    res = client.post("/api/submissions", json={"unit_key": "Q5", "answers": {"5": "a"}, **extra}, headers=students[0])
    assert res.status_code == 422


def test_error_codes_map_to_status(client, auth, sheets):
    activity, students = started(client, auth, sheets)
    s = students[0]
    assert submit(client, s, "Q9", {9: "a"}).status_code == 404
    res = submit(client, s, "G1", {1: "a"})
    assert res.status_code == 422 and res.json()["error"]["missing"] == [2]
    assert submit(client, s, "Q5", {5: "  "}).status_code == 422
    assert submit(client, s, "Q5", {5: "a"}).status_code == 200
    dup = submit(client, s, "Q5", {5: "b"})
    assert dup.status_code == 409 and dup.json()["error"]["code"] == "ALREADY_SUBMITTED"
    assert client.post("/api/submissions", json={"unit_key": "Q6", "answers": {"x": "a"}}, headers=s).status_code == 422
    client.post(f"/api/activities/{activity['id']}/end", headers=auth)
    late = submit(client, s, "Q6", {6: "a"})
    assert late.status_code == 409 and late.json()["error"]["message"] == "目前不在搶答時間。"


def test_submit_before_start_rejected(client, auth, sheets):
    activity = create_activity(client, auth, sheets)
    student = student_auth(client, activity["teams"][0]["code"])
    res = submit(client, student, "Q5", {5: "a"})
    assert res.status_code == 409 and res.json()["error"]["code"] == "NOT_RUNNING"


def test_cooldown_response_has_retry_after(client, auth, sheets):
    _, students = started(client, auth, sheets, cooldown_lead=1, cooldown_seconds=30)
    submit(client, students[0], "Q5", {5: "a"})
    res = submit(client, students[0], "Q6", {6: "b"})
    assert res.status_code == 409 and res.json()["error"]["code"] == "COOLDOWN"
    assert res.json()["error"]["retry_after_seconds"] == 30


def test_submit_without_token_401(client):
    assert client.post("/api/submissions", json={"unit_key": "Q5", "answers": {"5": "a"}}).status_code == 401


def test_same_team_other_window_receives_team_submission(client, auth, sheets):
    activity, students = started(client, auth, sheets)
    other_window = student_auth(client, activity["teams"][0]["code"], "second-window")
    with client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "auth", "token": other_window["Authorization"].split()[1]})
        ws.receive_json()
        submit(client, students[0], "Q5", {5: "CPU"})
        assert ws.receive_json() == {"type": "team_submission", "unit_key": "Q5", "rank": 1, "outcome": "success"}
