"""伺服器重啟（tasks T021、FR-026、FR-027）：同一個資料庫上建立兩個 app 實例。"""

from fastapi.testclient import TestClient

from guided_buzz.api.app import create_app
from tests.buzz import confirmed_b, join, started, submit
from tests.conftest import PASSWORD


def login(c) -> dict:
    return {"Authorization": f"Bearer {c.post('/api/auth/teacher-login', json={'password': PASSWORD}).json()['token']}"}


def test_running_activity_interrupted_after_restart(settings, sheets):
    with TestClient(create_app(settings, sheets)) as first:
        auth = login(first)
        activity, students = started(first, auth, sheets)
        submit(first, students[0], "Q5", {5: "CPU"})
        code = activity["teams"][0]["code"]
    with TestClient(create_app(settings, sheets)) as second:
        assert second.get(f"/api/activities/{activity['id']}/phase").json() == {"phase": "interrupted"}
        assert join(second, code).status_code == 401
        assert second.get("/api/me", headers=students[0]).status_code == 401
        auth = login(second)
        res = second.get(f"/api/activities/{activity['id']}", headers=auth)
        assert res.status_code == 409 and "已中斷" in res.json()["error"]["message"]
        wid = confirmed_b(second, auth, sheets)
        assert second.post("/api/activities", json={"worksheet_id": wid, "teams": ["A"]}, headers=auth).status_code == 201


def test_ended_results_survive_restart(settings, sheets):
    with TestClient(create_app(settings, sheets)) as first:
        auth = login(first)
        activity, students = started(first, auth, sheets)
        submit(first, students[0], "G1", {1: "CPU", 2: "作業系統"})
        submit(first, students[1], "G1", {1: "x", 2: "y"})
        first.post(f"/api/activities/{activity['id']}/end", headers=auth)
        before = first.get(f"/api/activities/{activity['id']}/results", headers=auth).json()
    with TestClient(create_app(settings, sheets)) as second:
        auth = login(second)
        assert second.get(f"/api/activities/{activity['id']}/phase").json() == {"phase": "ended"}
        after = second.get(f"/api/activities/{activity['id']}/results", headers=auth).json()
        assert after == before
        res = second.post(f"/api/activities/{activity['id']}/units/G1/invalidate", headers=auth)
        assert res.json()["promoted_team_id"] == 2  # 重啟後仍可判定無效
