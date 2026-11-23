"""002 搶答活動的測試工具：假時鐘、假 repository、建立引擎，以及 API 層的共用流程。"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from guided_buzz.activity import codes
from guided_buzz.activity.engine import ActivityEngine
from guided_buzz.activity.state import ActivityInfo, TeamState
from guided_buzz.domain.models import ActivityPhase, BuzzUnit

SAMPLE_B = "1PXXwWiBKJNpPkLRoJLMzZWsAh4Jzn2bThHTeRAiq3Hg"

# 範例 B 的 4 個搶答單位
UNITS_B = [
    BuzzUnit("G1", (1, 2), "題組 1：第 1、2 題"),
    BuzzUnit("G2", (3, 4), "題組 2：第 3、4 題"),
    BuzzUnit("Q5", (5,), "第 5 題"),
    BuzzUnit("Q6", (6,), "第 6 題"),
]


class FakeClock:
    def __init__(self):
        self.mono = 1000.0
        self.wall = datetime(2026, 11, 23, 9, 0, tzinfo=timezone.utc)

    def monotonic(self) -> float:
        return self.mono

    def now(self) -> datetime:
        return self.wall

    def advance(self, seconds: float) -> None:
        self.mono += seconds
        self.wall += timedelta(seconds=seconds)


class FakeRepo:
    def __init__(self):
        self.calls: list[tuple] = []
        self.fail_persist = False

    def update_phase(self, activity_id, phase, *, started_at=None, ended_at=None):
        self.calls.append(("phase", phase))

    def persist_results(self, activity_id, submissions, ended_at):
        if self.fail_persist:
            raise OSError("disk full")
        self.calls.append(("persist", len(submissions)))

    def update_invalidation(self, activity_id, invalidated_id, invalidated_at, promoted_id):
        self.calls.append(("invalidate", invalidated_id, promoted_id))

    def update_team_code(self, activity_id, team_id, code_hash, code_version):
        self.calls.append(("code", team_id, code_version))


def make_engine(teams=3, units=None, *, fairness=True, n=10, k=2, max_len=200, phase=ActivityPhase.PREPARING, repo=None, clock=None) -> ActivityEngine:
    clock = clock or FakeClock()
    info = ActivityInfo(uuid4(), uuid4(), "teacher", phase, fairness, n, k, clock.now())
    states = {}
    for i in range(1, teams + 1):
        code = codes.new_code({t.code for t in states.values()})
        states[i] = TeamState(i, f"第{i}組", codes.code_hash(code), 1, code)
    return ActivityEngine(info, list(UNITS_B if units is None else units), states, repo or FakeRepo(), max_len, clock)


async def running(**kw) -> ActivityEngine:
    engine = make_engine(**kw)
    await engine.start()
    return engine


def ans(*pairs) -> dict[int, str]:
    """ans(5, "CPU") → {5: "CPU"}；ans(1, "a", 2, "b") → {1: "a", 2: "b"}。"""
    return {pairs[i]: pairs[i + 1] for i in range(0, len(pairs), 2)}


# ---------- API 層 ----------


def confirmed_b(client, auth, sheets) -> str:
    sheets.add_fixture("sample_b")
    wid = client.post("/api/worksheets", json={"spreadsheet_url": SAMPLE_B}, headers=auth).json()["id"]
    client.post(f"/api/worksheets/{wid}/confirm", headers=auth)
    return wid


def create_activity(client, auth, sheets, teams=("第一組", "第二組", "第三組"), **extra) -> dict:
    wid = confirmed_b(client, auth, sheets)
    res = client.post("/api/activities", json={"worksheet_id": wid, "teams": list(teams), **extra}, headers=auth)
    assert res.status_code == 201, res.text
    return res.json()


def join(client, code, window="w-default"):
    return client.post("/api/join", json={"code": code}, headers={"X-Window-Id": window})


def student_auth(client, code, window="w-default") -> dict:
    res = join(client, code, window)
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['token']}"}


def started(client, auth, sheets, **kw) -> tuple[dict, list[dict]]:
    """建立並開始活動，回傳 (活動, 各組學生的 auth 標頭)。"""
    activity = create_activity(client, auth, sheets, **kw)
    students = [student_auth(client, t["code"], f"w{t['id']}") for t in activity["teams"]]
    assert client.post(f"/api/activities/{activity['id']}/start", headers=auth).status_code == 200
    return activity, students


def submit(client, student, unit_key, answers: dict):
    return client.post("/api/submissions", json={"unit_key": unit_key, "answers": {str(k): v for k, v in answers.items()}}, headers=student)
