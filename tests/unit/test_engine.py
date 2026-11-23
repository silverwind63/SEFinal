"""ActivityEngine：階段（T017）、送出（T031）、判定無效（T038）、檢視（T046）、冷卻互動（T052）。"""

import pytest

from guided_buzz.domain.errors import InvalidState, NotEnded, NotFound, PersistFailed, SubmissionRejectCode, SubmissionRejected
from guided_buzz.domain.models import ActivityPhase
from tests.buzz import FakeClock, FakeRepo, ans, make_engine, running


def reject_code(exc_info) -> SubmissionRejectCode:
    return exc_info.value.reject_code


# ---------- 階段（T017） ----------


async def test_phase_flow_preparing_running_ended():
    repo = FakeRepo()
    engine = make_engine(repo=repo)
    events = await engine.start()
    assert engine.phase is ActivityPhase.RUNNING
    assert events[0].payload == {"type": "phase_changed", "phase": "running"}
    await engine.end()
    assert engine.phase is ActivityPhase.ENDED
    assert ("persist", 0) in repo.calls


@pytest.mark.parametrize("action", ["end", "start_twice"])
async def test_disallowed_transitions(action):
    engine = make_engine()
    with pytest.raises(InvalidState):
        if action == "end":
            await engine.end()  # 準備中不能結束
        else:
            await engine.start()
            await engine.start()


async def test_cannot_restart_after_end():
    engine = await running()
    await engine.end()
    with pytest.raises(InvalidState):
        await engine.start()


@pytest.mark.parametrize("teams,units", [(0, None), (3, [])])
async def test_cannot_start_without_teams_or_units(teams, units):
    engine = make_engine(teams=teams, units=units)
    with pytest.raises(InvalidState):
        await engine.start()


async def test_end_keeps_running_when_persist_fails():
    repo = FakeRepo()
    engine = await running(repo=repo)
    await engine.submit(1, 1, "Q5", ans(5, "CPU"))
    repo.fail_persist = True
    with pytest.raises(PersistFailed):
        await engine.end()
    assert engine.phase is ActivityPhase.RUNNING
    repo.fail_persist = False
    await engine.end()
    assert engine.phase is ActivityPhase.ENDED


# ---------- 送出（T031） ----------


async def test_first_success_second_not_won():
    engine = await running()
    r1, events = await engine.submit(1, 1, "Q5", ans(5, "CPU"))
    r2, _ = await engine.submit(2, 1, "Q5", ans(5, "GPU"))
    assert (r1["outcome"], r1["rank"], r1["message"]) == ("success", 1, "搶答成功！")
    assert (r2["outcome"], r2["rank"], r2["message"]) == ("not_won", 2, "未搶到，第 2 順位")
    assert {e.audience for e in events} >= {"team", "teacher"}


async def test_group_submitted_together():
    engine = await running()
    r, _ = await engine.submit(1, 1, "G1", ans(1, "CPU", 2, "作業系統"))
    assert r["outcome"] == "success"
    assert engine.submissions[0].answers == {1: "CPU", 2: "作業系統"}


async def test_answers_are_trimmed():
    engine = await running()
    await engine.submit(1, 1, "Q5", ans(5, "  CPU \n"))
    assert engine.submissions[0].answers == {5: "CPU"}


@pytest.mark.parametrize(
    "setup,call,code",
    [
        ("preparing", (1, 1, "Q5", {5: "a"}), SubmissionRejectCode.NOT_RUNNING),
        ("ended", (1, 1, "Q5", {5: "a"}), SubmissionRejectCode.NOT_RUNNING),
        ("running", (1, 2, "Q5", {5: "a"}), SubmissionRejectCode.UNAUTHORIZED),  # 代碼版本過期
        ("running", (9, 1, "Q5", {5: "a"}), SubmissionRejectCode.UNAUTHORIZED),  # 不存在的組別
        ("running", (1, 1, "Q9", {9: "a"}), SubmissionRejectCode.UNKNOWN_UNIT),
        ("running", (1, 1, "G1", {1: "a"}), SubmissionRejectCode.INCOMPLETE_GROUP),  # 少一題
        ("running", (1, 1, "G1", {1: "a", 2: "b", 3: "c"}), SubmissionRejectCode.INCOMPLETE_GROUP),  # 多一題
        ("running", (1, 1, "Q5", {5: "   "}), SubmissionRejectCode.INVALID_ANSWER),
        ("running", (1, 1, "Q5", {5: ""}), SubmissionRejectCode.INVALID_ANSWER),
        ("running", (1, 1, "Q5", {5: "x" * 11}), SubmissionRejectCode.INVALID_ANSWER),
    ],
)
async def test_rejections_leave_no_record(setup, call, code):
    engine = make_engine(max_len=10)
    if setup != "preparing":
        await engine.start()
    if setup == "ended":
        await engine.end()
    with pytest.raises(SubmissionRejected) as e:
        await engine.submit(*call)
    assert reject_code(e) is code
    assert engine.submissions == []


async def test_incomplete_group_lists_missing_and_unexpected():
    engine = await running()
    with pytest.raises(SubmissionRejected) as e:
        await engine.submit(1, 1, "G1", {1: "a", 5: "b"})
    assert e.value.extra == {"missing": [2], "unexpected": [5]}
    assert "缺少第 2 題" in e.value.message


async def test_answer_length_boundary():
    engine = await running(max_len=10)
    r, _ = await engine.submit(1, 1, "Q5", {5: "x" * 10})
    assert r["outcome"] == "success"


async def test_same_team_cannot_submit_twice():
    engine = await running()
    await engine.submit(1, 1, "Q5", ans(5, "a"))
    with pytest.raises(SubmissionRejected) as e:
        await engine.submit(1, 1, "Q5", ans(5, "b"))
    assert reject_code(e) is SubmissionRejectCode.ALREADY_SUBMITTED
    assert len(engine.submissions) == 1


# ---------- 判定無效（T038） ----------


async def test_invalidate_promotes_next_rank():
    engine = await running()
    await engine.submit(1, 1, "Q5", ans(5, "a"))
    await engine.submit(2, 1, "Q5", ans(5, "b"))
    result, events = await engine.invalidate("Q5")
    assert result == {"unit_key": "Q5", "invalidated_team_id": 1, "promoted_team_id": 2, "unit_status": "won"}
    assert [s.outcome.value for s in engine.submissions] == ["invalidated", "success"]
    team_events = {(e.team_id, e.payload["type"]) for e in events if e.audience == "team"}
    assert team_events == {(1, "invalidated"), (2, "promoted")}
    assert all("b" not in str(e.payload) for e in events if e.audience == "team" and e.team_id == 1)


async def test_invalidate_without_successor_reopens_while_running():
    engine = await running()
    await engine.submit(1, 1, "Q5", ans(5, "a"))
    result, _ = await engine.invalidate("Q5")
    assert result["promoted_team_id"] is None and result["unit_status"] == "open"
    with pytest.raises(SubmissionRejected) as e:
        await engine.submit(1, 1, "Q5", ans(5, "again"))
    assert reject_code(e) is SubmissionRejectCode.ALREADY_SUBMITTED
    r, _ = await engine.submit(3, 1, "Q5", ans(5, "c"))
    assert (r["outcome"], r["rank"]) == ("success", 2)


async def test_invalidate_after_end_marks_no_winner_and_persists():
    repo = FakeRepo()
    engine = await running(repo=repo)
    await engine.submit(1, 1, "Q5", ans(5, "a"))
    await engine.end()
    result, _ = await engine.invalidate("Q5")
    assert result["unit_status"] == "no_winner"
    assert ("invalidate", 1, None) in repo.calls


async def test_invalidate_twice_in_a_row():
    engine = await running()
    for team in (1, 2, 3):
        await engine.submit(team, 1, "Q5", ans(5, f"t{team}"))
    await engine.invalidate("Q5")
    result, _ = await engine.invalidate("Q5")
    assert result["promoted_team_id"] == 3
    assert engine.view_for_teacher()["teams"][2]["wins"] == 1
    assert engine.view_for_teacher()["teams"][0]["wins"] == 0


async def test_invalidate_unit_without_winner_or_unknown():
    engine = await running()
    with pytest.raises(InvalidState):
        await engine.invalidate("Q5")
    with pytest.raises(NotFound):
        await engine.invalidate("Q9")


async def test_cannot_invalidate_while_preparing():
    with pytest.raises(InvalidState):
        await make_engine().invalidate("Q5")


# ---------- 檢視（T046） ----------


async def test_team_view_only_contains_own_submissions_while_running():
    engine = await running()
    await engine.submit(1, 1, "Q5", ans(5, "秘密答案"))
    view = engine.view_for_team(2)
    assert view["my_submissions"] == [] and view["results"] is None
    assert "秘密答案" not in str(view) and "第1組" not in str(view)
    assert all(set(u) == {"key", "display", "question_nos"} for u in view["units"])  # 看不出哪些單位已被搶走
    with pytest.raises(NotEnded):
        engine.results_view(include_all=False)


async def test_results_after_end():
    engine = await running()
    await engine.submit(1, 1, "G1", ans(1, "CPU", 2, "OS"))
    await engine.submit(2, 1, "G1", ans(1, "x", 2, "y"))
    await engine.end()
    view = engine.view_for_team(3)
    units = {u["key"]: u for u in view["results"]["units"]}
    assert units["G1"]["winner"] == {"team_id": 1, "team_name": "第1組", "answers": {"1": "CPU", "2": "OS"}}
    assert units["Q5"]["status"] == "no_winner" and units["Q5"]["winner"] is None
    assert "submissions" not in units["G1"]  # 學生看不到所有送出
    assert [t["wins"] for t in view["results"]["teams"]] == [1, 0, 0]
    assert len(engine.results_view(include_all=True)["units"][0]["submissions"]) == 2


async def test_teacher_codes_hidden_after_end():
    engine = await running()
    assert all(t["code"] for t in engine.view_for_teacher()["teams"])
    await engine.end()
    assert all(t["code"] is None for t in engine.view_for_teacher()["teams"])


# ---------- 冷卻與判定無效的互動（T052） ----------


async def test_invalidating_trigger_success_releases_cooldown():
    clock = FakeClock()
    engine = await running(clock=clock, k=2, n=10)
    await engine.submit(1, 1, "Q5", ans(5, "a"))
    await engine.submit(1, 1, "Q6", ans(6, "b"))  # 領先 2 題 → 冷卻
    assert engine.view_for_team(1)["cooldown_remaining"] == 10
    _, events = await engine.invalidate("Q6")
    assert engine.view_for_team(1)["cooldown_remaining"] == 0
    assert any(e.payload == {"type": "cooldown", "team_id": 1, "active": False, "remaining_seconds": 0} for e in events)


async def test_promotion_does_not_trigger_cooldown():
    engine = await running(k=1, n=10)
    await engine.submit(1, 1, "Q5", ans(5, "a"))  # 第1組領先 1 → 冷卻
    await engine.submit(2, 1, "Q6", ans(6, "x"))  # 第2組成功，最少成功數仍為 0（第3組）→ 第2組也冷卻
    await engine.submit(3, 1, "Q6", ans(6, "y"))  # not_won
    await engine.invalidate("Q6")  # 第3組遞補
    assert engine.view_for_team(3)["cooldown_remaining"] == 0


async def test_cooldown_rejection_does_not_take_rank_and_can_retry_later():
    clock = FakeClock()
    engine = await running(clock=clock, k=1, n=10)
    await engine.submit(1, 1, "Q5", ans(5, "a"))
    with pytest.raises(SubmissionRejected) as e:
        await engine.submit(1, 1, "Q6", ans(6, "b"))
    assert reject_code(e) is SubmissionRejectCode.COOLDOWN and e.value.extra == {"retry_after_seconds": 10}
    r, _ = await engine.submit(2, 1, "Q6", ans(6, "c"))
    assert r["rank"] == 1  # 冷卻中被拒的送出不佔順位
    clock.advance(10)
    r, _ = await engine.submit(1, 1, "Q6", ans(6, "b"))
    assert (r["outcome"], r["rank"]) == ("not_won", 2)


async def test_regenerate_code_bumps_version_and_revokes():
    repo = FakeRepo()
    engine = make_engine(repo=repo)
    old = engine.teams[1].code
    code, events = await engine.regenerate_code(1)
    assert code != old and engine.teams[1].code_version == 2
    assert events[0].audience == "revoke" and events[0].team_id == 1
    assert engine.find_team_by_code(old) is None and engine.find_team_by_code(code).id == 1
    await engine.start()
    with pytest.raises(SubmissionRejected):
        await engine.submit(1, 1, "Q5", ans(5, "a"))
