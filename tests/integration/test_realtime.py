"""WebSocket 即時同步（tasks T020、contracts/websocket.md）。"""

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from guided_buzz.api.app import create_app
from guided_buzz.config import load_settings
from tests.buzz import create_activity, student_auth


def bearer(headers: dict) -> str:
    return headers["Authorization"].split()[1]


def test_invalid_token_closed_4401(client):
    with client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "auth", "token": "nope"})
        with pytest.raises(WebSocketDisconnect) as e:
            ws.receive_json()
        assert e.value.code == 4401


def test_no_auth_message_closed_after_timeout(tmp_path, sheets, settings):
    env = {"GB_TEACHER_PASSWORD": "pw", "GB_GOOGLE_OAUTH_CLIENT_FILE": str(settings.google_oauth_client_file), "GB_DATA_DIR": str(tmp_path / "d2"), "GB_WS_AUTH_TIMEOUT_SECONDS": "0.2"}
    with TestClient(create_app(load_settings(env), sheets)) as c, c.websocket_connect("/ws") as ws:
        with pytest.raises(WebSocketDisconnect) as e:
            ws.receive_json()
        assert e.value.code == 4401


def test_snapshot_first_then_phase_changed_for_everyone(client, auth, token, sheets):
    activity = create_activity(client, auth, sheets)
    s1 = student_auth(client, activity["teams"][0]["code"], "w1")
    s2 = student_auth(client, activity["teams"][1]["code"], "w2")
    with client.websocket_connect("/ws") as t, client.websocket_connect("/ws") as a, client.websocket_connect("/ws") as b:
        t.send_json({"type": "auth", "token": token})
        a.send_json({"type": "auth", "token": bearer(s1)})
        b.send_json({"type": "auth", "token": bearer(s2)})
        teacher_snap, snap_a, snap_b = t.receive_json(), a.receive_json(), b.receive_json()
        assert teacher_snap["type"] == "snapshot" and teacher_snap["activity"]["id"] == activity["id"]
        assert snap_a["team"]["id"] == 1 and snap_b["team"]["id"] == 2
        assert "code" not in str(snap_a["team"])
        client.post(f"/api/activities/{activity['id']}/start", headers=auth)
        for ws in (t, a, b):
            assert ws.receive_json() == {"type": "phase_changed", "phase": "running"}


def test_reconnect_gets_fresh_snapshot(client, auth, sheets):
    activity = create_activity(client, auth, sheets)
    s1 = student_auth(client, activity["teams"][0]["code"])
    with client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "auth", "token": bearer(s1)})
        assert ws.receive_json()["phase"] == "preparing"
    client.post(f"/api/activities/{activity['id']}/start", headers=auth)
    with client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "auth", "token": bearer(s1)})
        assert ws.receive_json()["phase"] == "running"


def test_teacher_and_student_connections_keep_own_identity(client, auth, token, sheets):
    """同一個瀏覽器的兩個視窗：一個老師、一個第一組，身分互不影響（FR-005a）。"""
    activity = create_activity(client, auth, sheets)
    s1 = student_auth(client, activity["teams"][0]["code"])
    with client.websocket_connect("/ws") as t, client.websocket_connect("/ws") as a:
        t.send_json({"type": "auth", "token": token})
        a.send_json({"type": "auth", "token": bearer(s1)})
        assert "activity" in t.receive_json()
        assert a.receive_json()["team"]["name"] == "第一組"
    assert client.get("/api/activities", headers=auth).status_code == 200
    assert client.get("/api/me", headers=s1).json()["team"]["id"] == 1


def test_end_sends_results_snapshot_to_students(client, auth, sheets):
    activity = create_activity(client, auth, sheets)
    s1 = student_auth(client, activity["teams"][0]["code"])
    client.post(f"/api/activities/{activity['id']}/start", headers=auth)
    client.post("/api/submissions", json={"unit_key": "Q5", "answers": {"5": "CPU"}}, headers=s1)
    with client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "auth", "token": bearer(s1)})
        ws.receive_json()
        client.post(f"/api/activities/{activity['id']}/end", headers=auth)
        assert ws.receive_json() == {"type": "phase_changed", "phase": "ended"}
        snap = ws.receive_json()
    assert snap["type"] == "snapshot" and snap["results"]["units"][2]["winner"]["answers"] == {"5": "CPU"}
