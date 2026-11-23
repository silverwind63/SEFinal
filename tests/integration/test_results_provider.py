"""002 結果接上 001 的寫回與 CSV 匯出（tasks T057–T059、FR-017）。"""

import csv
import io

import pytest
from fastapi.testclient import TestClient

from guided_buzz.api.app import create_app
from guided_buzz.config import load_settings
from guided_buzz.results.sqlite_provider import SqliteActivityResultsProvider
from guided_buzz.domain.errors import NotFound
from tests.buzz import started, submit
from tests.conftest import PASSWORD


@pytest.fixture
def db_client(tmp_path, sheets, settings):
    """不設定 GB_RESULTS_DIR：001 的寫回與匯出預設讀取 002 保存的結果。"""
    env = {"GB_TEACHER_PASSWORD": PASSWORD, "GB_GOOGLE_OAUTH_CLIENT_FILE": str(settings.google_oauth_client_file), "GB_DATA_DIR": str(tmp_path / "db-data")}
    with TestClient(create_app(load_settings(env), sheets)) as c:
        yield c


@pytest.fixture
def db_auth(db_client):
    return {"Authorization": f"Bearer {db_client.post('/api/auth/teacher-login', json={'password': PASSWORD}).json()['token']}"}


def play(client, auth, sheets):
    activity, s = started(client, auth, sheets, fairness_enabled=False)
    aid = activity["id"]
    submit(client, s[0], "G1", {1: "CPU", 2: "作業系統"})
    submit(client, s[1], "G1", {1: "x", 2: "y"})
    submit(client, s[1], "Q5", {5: "1, 也許"})
    submit(client, s[2], "Q5", {5: "0"})
    client.post(f"/api/activities/{aid}/units/Q5/invalidate", headers=auth)  # 第三組遞補
    return activity


def test_writeback_and_csv_match_results_view(db_client, db_auth, sheets):
    activity = play(db_client, db_auth, sheets)
    aid, wid = activity["id"], activity["worksheet_id"]
    assert db_client.post(f"/api/worksheets/{wid}/writeback", json={"activity_id": aid}, headers=db_auth).status_code == 409  # 未結束
    db_client.post(f"/api/activities/{aid}/end", headers=db_auth)

    results = db_client.get(f"/api/activities/{aid}/results", headers=db_auth).json()
    winners = {u["key"]: u["winner"] for u in results["units"]}
    assert winners["G1"]["team_name"] == "第一組" and winners["Q5"]["team_name"] == "第三組"

    res = db_client.post(f"/api/worksheets/{wid}/writeback", json={"activity_id": aid}, headers=db_auth)
    assert res.status_code == 200
    assert res.json() == {"filled": [1, 2, 5], "unfilled": [3, 4, 6], "skipped_non_empty": []}
    _, written = sheets.writes[-1]
    assert {r.cell: t for r, t in written.items()} == {"H5": "CPU", "H6": "作業系統", "G11": "0"}

    text = db_client.get(f"/api/activities/{aid}/results.csv", headers=db_auth).content.decode("utf-8-sig")
    rows = list(csv.reader(io.StringIO(text)))
    assert rows[0] == ["題號", "組別", "答案", "搶答順位", "結果"]
    assert rows[1:] == [
        ["1", "第一組", "CPU", "1", "成功"],
        ["1", "第二組", "x", "2", "未搶到"],
        ["2", "第一組", "作業系統", "1", "成功"],
        ["2", "第二組", "y", "2", "未搶到"],
        ["5", "第二組", "1, 也許", "1", "無效"],
        ["5", "第三組", "0", "2", "成功"],
    ]


def test_provider_not_found_and_not_ended(db_client, db_auth, sheets):
    activity = play(db_client, db_auth, sheets)
    provider = SqliteActivityResultsProvider(db_client.app.state.registry.repo)
    assert provider.get_result(activity["id"], "teacher").ended is False
    with pytest.raises(NotFound):
        provider.get_result(activity["id"], "someone-else")
    with pytest.raises(NotFound):
        provider.get_result("not-a-uuid", "teacher")
