"""結束前學生看不到他組資料（tasks T045、FR-014、SC-003）。"""

from tests.buzz import started, submit

SECRET = "第一組的秘密答案"


def leaks_team1(payload) -> bool:
    text = str(payload)
    return SECRET in text or "第一組" in text or "'team_id': 1" in text


def test_second_team_cannot_see_first_team_anything(client, auth, sheets):
    activity, students = started(client, auth, sheets)
    aid = activity["id"]
    t1, t2 = students[0], students[1]
    with client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "auth", "token": t2["Authorization"].split()[1]})
        snap = ws.receive_json()
        submit(client, t1, "Q5", {5: SECRET})
        submit(client, t1, "G1", {1: SECRET, 2: SECRET})
        submit(client, t2, "Q6", {6: "第二組自己的"})
        own = ws.receive_json()  # 第一組的事件若外洩，會排在這則之前
    assert not leaks_team1(snap)
    assert own == {"type": "team_submission", "unit_key": "Q6", "rank": 1, "outcome": "success"}

    me = client.get("/api/me", headers=t2).json()
    assert not leaks_team1(me)
    assert all(set(u) == {"key", "display", "question_nos"} for u in me["units"])  # 看不出 Q5、G1 已被搶走

    res = client.get(f"/api/activities/{aid}/results", headers=t2)
    assert res.status_code == 409 and res.json()["error"]["code"] == "NOT_ENDED"
    for path in (f"/api/activities/{aid}", "/api/activities", f"/api/activities/{aid}/results.csv"):
        assert client.get(path, headers=t2).status_code == 401
    assert client.get(f"/api/activities/{aid}/phase").json() == {"phase": "running"}  # 公開端點只有階段


def test_student_of_other_activity_cannot_read_results(client, auth, sheets):
    activity, students = started(client, auth, sheets)
    client.post(f"/api/activities/{activity['id']}/end", headers=auth)
    res = client.get("/api/activities/00000000-0000-0000-0000-000000000000/results", headers=students[0])
    assert res.status_code == 401


def test_results_visible_to_students_after_end(client, auth, sheets):
    activity, students = started(client, auth, sheets)
    aid = activity["id"]
    submit(client, students[0], "Q5", {5: SECRET})
    client.post(f"/api/activities/{aid}/end", headers=auth)
    res = client.get(f"/api/activities/{aid}/results", headers=students[1])
    assert res.status_code == 200
    q5 = next(u for u in res.json()["units"] if u["key"] == "Q5")
    assert q5["winner"] == {"team_id": 1, "team_name": "第一組", "answers": {"5": SECRET}}
    assert "submissions" not in q5
    teacher = client.get(f"/api/activities/{aid}/results", headers=auth).json()
    assert "submissions" in teacher["units"][0]
