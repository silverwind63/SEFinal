"""即時同步延遲（tasks T060、SC-001）：1 個老師與 12 個學生連線，2 秒內收到更新。"""

import time
from contextlib import ExitStack

from tests.buzz import create_activity, student_auth, submit

LIMIT_SECONDS = 2.0


def test_thirteen_connections_receive_updates_within_two_seconds(client, auth, token, sheets):
    activity = create_activity(client, auth, sheets, teams=[f"第{i}組" for i in range(1, 7)])
    students = [student_auth(client, t["code"], f"w{t['id']}-{n}") for t in activity["teams"] for n in (1, 2)]
    with ExitStack() as stack:
        teacher = stack.enter_context(client.websocket_connect("/ws"))
        teacher.send_json({"type": "auth", "token": token})
        teacher.receive_json()
        conns = []
        for s in students:
            ws = stack.enter_context(client.websocket_connect("/ws"))
            ws.send_json({"type": "auth", "token": s["Authorization"].split()[1]})
            ws.receive_json()
            conns.append(ws)

        started_at = time.monotonic()
        client.post(f"/api/activities/{activity['id']}/start", headers=auth)
        for ws in [teacher, *conns]:
            assert ws.receive_json()["type"] == "phase_changed"
        assert time.monotonic() - started_at < LIMIT_SECONDS

        sent_at = time.monotonic()
        submit(client, students[0], "Q5", {5: "CPU"})
        assert teacher.receive_json()["type"] == "submission"
        assert time.monotonic() - sent_at < LIMIT_SECONDS
