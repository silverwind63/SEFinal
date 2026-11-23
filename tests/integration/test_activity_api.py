"""老師端 API（tasks T018、T039）。"""

import pytest
from starlette.websockets import WebSocketDisconnect

from tests.buzz import confirmed_b, create_activity, join, started, student_auth, submit


def test_create_activity_returns_codes_and_units(client, auth, sheets):
    activity = create_activity(client, auth, sheets)
    assert activity["phase"] == "preparing"
    assert [u["key"] for u in activity["units"]] == ["G1", "G2", "Q5", "Q6"]
    codes = [t["code"] for t in activity["teams"]]
    assert len(set(codes)) == 3 and all(len(c) == 6 for c in codes)
    assert activity["fairness"] == {"enabled": True, "cooldown_seconds": 10, "cooldown_lead": 2}


def test_create_with_fairness_overrides(client, auth, sheets):
    activity = create_activity(client, auth, sheets, fairness_enabled=False, cooldown_seconds=30, cooldown_lead=3)
    assert activity["fairness"] == {"enabled": False, "cooldown_seconds": 30, "cooldown_lead": 3}


def test_unconfirmed_worksheet_rejected(client, auth, sheets):
    sheets.add_fixture("sample_b")
    wid = client.post("/api/worksheets", json={"spreadsheet_url": "1PXXwWiBKJNpPkLRoJLMzZWsAh4Jzn2bThHTeRAiq3Hg"}, headers=auth).json()["id"]
    res = client.post("/api/activities", json={"worksheet_id": wid, "teams": ["A"]}, headers=auth)
    assert res.status_code == 409 and res.json()["error"]["code"] == "INVALID_STATE"


def test_unknown_worksheet_404(client, auth):
    res = client.post("/api/activities", json={"worksheet_id": "00000000-0000-0000-0000-000000000000", "teams": ["A"]}, headers=auth)
    assert res.status_code == 404


def test_second_live_activity_rejected(client, auth, sheets):
    activity = create_activity(client, auth, sheets)
    res = client.post("/api/activities", json={"worksheet_id": activity["worksheet_id"], "teams": ["A"]}, headers=auth)
    assert res.status_code == 409 and res.json()["error"]["code"] == "ACTIVITY_IN_PROGRESS"


@pytest.mark.parametrize(
    "teams,fragment",
    [
        (["A", "A"], "組名不可重複"),
        (["A", "  "], "不可為空白"),
        (["A", "x" * 21], "超過 20 字"),
        ([f"T{i}" for i in range(21)], "組數必須是 1–20 組"),
    ],
)
def test_invalid_team_names(client, auth, sheets, teams, fragment):
    wid = confirmed_b(client, auth, sheets)
    res = client.post("/api/activities", json={"worksheet_id": wid, "teams": teams}, headers=auth)
    assert res.status_code == 422 and fragment in res.json()["error"]["message"]


@pytest.mark.parametrize("extra", [{"cooldown_seconds": 0}, {"cooldown_lead": 101}, {"surprise": 1}])
def test_invalid_overrides(client, auth, sheets, extra):
    wid = confirmed_b(client, auth, sheets)
    res = client.post("/api/activities", json={"worksheet_id": wid, "teams": ["A"], **extra}, headers=auth)
    assert res.status_code == 422


def test_student_token_cannot_call_teacher_endpoints(client, auth, sheets):
    activity = create_activity(client, auth, sheets)
    student = student_auth(client, activity["teams"][0]["code"])
    aid = activity["id"]
    for method, path in [("post", f"/api/activities/{aid}/start"), ("get", f"/api/activities/{aid}"), ("post", f"/api/activities/{aid}/units/Q5/invalidate")]:
        assert getattr(client, method)(path, headers=student).status_code == 401


def test_start_and_end_status_codes(client, auth, sheets):
    activity = create_activity(client, auth, sheets)
    aid = activity["id"]
    assert client.post(f"/api/activities/{aid}/end", headers=auth).status_code == 409
    assert client.post(f"/api/activities/{aid}/start", headers=auth).json() == {"phase": "running"}
    assert client.post(f"/api/activities/{aid}/start", headers=auth).status_code == 409
    assert client.post(f"/api/activities/{aid}/end", headers=auth).json() == {"phase": "ended"}
    assert client.post(f"/api/activities/{aid}/start", headers=auth).status_code == 409
    listed = client.get("/api/activities", headers=auth).json()
    assert listed[0]["id"] == aid and listed[0]["phase"] == "ended"


def test_new_activity_allowed_after_end(client, auth, sheets):
    activity = create_activity(client, auth, sheets)
    client.post(f"/api/activities/{activity['id']}/start", headers=auth)
    client.post(f"/api/activities/{activity['id']}/end", headers=auth)
    res = client.post("/api/activities", json={"worksheet_id": activity["worksheet_id"], "teams": ["A"]}, headers=auth)
    assert res.status_code == 201


def test_regenerate_code_invalidates_old_code_and_sessions(client, auth, sheets):
    activity = create_activity(client, auth, sheets)
    aid, old = activity["id"], activity["teams"][0]["code"]
    student = student_auth(client, old)
    with client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "auth", "token": student["Authorization"].split()[1]})
        assert ws.receive_json()["type"] == "snapshot"
        res = client.post(f"/api/activities/{aid}/teams/1/regenerate-code", headers=auth)
        assert res.status_code == 200 and res.json()["code"] != old
        assert ws.receive_json() == {"type": "session_revoked", "reason": "code_regenerated"}
        with pytest.raises(WebSocketDisconnect) as e:
            ws.receive_json()
        assert e.value.code == 4403
    assert join(client, old).status_code == 401
    assert client.get("/api/me", headers=student).status_code == 401
    assert join(client, res.json()["code"]).status_code == 200


def test_teacher_view_and_invalidate_flow(client, auth, sheets):
    activity, students = started(client, auth, sheets)
    aid = activity["id"]
    submit(client, students[0], "Q5", {5: "CPU"})
    submit(client, students[1], "Q5", {5: "GPU"})
    view = client.get(f"/api/activities/{aid}", headers=auth).json()
    q5 = next(u for u in view["units"] if u["key"] == "Q5")
    assert [(s["team_name"], s["rank"], s["outcome"]) for s in q5["submissions"]] == [("第一組", 1, "success"), ("第二組", 2, "not_won")]
    assert [t["wins"] for t in view["teams"]] == [1, 0, 0]
    res = client.post(f"/api/activities/{aid}/units/Q5/invalidate", headers=auth)
    assert res.json() == {"unit_key": "Q5", "invalidated_team_id": 1, "promoted_team_id": 2, "unit_status": "won"}
    assert client.post(f"/api/activities/{aid}/units/Q6/invalidate", headers=auth).status_code == 409
    assert client.post(f"/api/activities/{aid}/units/Q9/invalidate", headers=auth).status_code == 404


def test_invalidate_after_end_is_persisted(client, auth, sheets):
    activity, students = started(client, auth, sheets)
    aid = activity["id"]
    submit(client, students[0], "Q6", {6: "a"})
    submit(client, students[2], "Q6", {6: "c"})
    client.post(f"/api/activities/{aid}/end", headers=auth)
    client.post(f"/api/activities/{aid}/units/Q6/invalidate", headers=auth)
    registry = client.app.state.registry
    stored = {s.team_id: s.outcome.value for s in registry.repo.load_submissions(registry.get(aid).id)}
    assert stored == {1: "invalidated", 3: "success"}


def test_invalidated_and_promoted_teams_notified_without_other_answers(client, auth, sheets):
    activity, students = started(client, auth, sheets)
    aid = activity["id"]
    submit(client, students[0], "Q5", {5: "第一組的答案"})
    submit(client, students[1], "Q5", {5: "第二組的答案"})
    tokens = [s["Authorization"].split()[1] for s in students[:2]]
    with client.websocket_connect("/ws") as ws1, client.websocket_connect("/ws") as ws2:
        for ws, t in ((ws1, tokens[0]), (ws2, tokens[1])):
            ws.send_json({"type": "auth", "token": t})
            ws.receive_json()
        client.post(f"/api/activities/{aid}/units/Q5/invalidate", headers=auth)
        m1, m2 = ws1.receive_json(), ws2.receive_json()
    assert m1["type"] == "invalidated" and "第二組的答案" not in str(m1)
    assert m2["type"] == "promoted" and "第一組的答案" not in str(m2)
