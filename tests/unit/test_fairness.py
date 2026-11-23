"""公平機制（tasks T051、spec US5 驗收情境 1–5），使用假時鐘。"""

import pytest

from guided_buzz.activity import fairness
from guided_buzz.domain.errors import SubmissionRejectCode, SubmissionRejected
from tests.buzz import FakeClock, ans, running

UNITS = [("Q5", 5), ("Q6", 6)]


def test_should_cooldown_rule():
    assert fairness.should_cooldown(2, 0, 2, True)
    assert not fairness.should_cooldown(1, 0, 2, True)
    assert not fairness.should_cooldown(5, 0, 2, False)  # 停用


def test_remaining_rounds_up_and_expires():
    assert fairness.remaining(1010.0, 1000.0) == 10
    assert fairness.remaining(1010.0, 1009.9) == 1  # N 秒的前一刻仍有效
    assert fairness.remaining(1010.0, 1010.0) == 0  # 到了 N 秒就解除


async def test_scenario_1_lead_two_triggers_cooldown():
    engine = await running(k=2, n=10)
    await engine.submit(1, 1, "Q5", ans(5, "a"))
    assert engine.view_for_team(1)["cooldown_remaining"] == 0
    _, events = await engine.submit(1, 1, "Q6", ans(6, "b"))
    assert engine.view_for_team(1)["cooldown_remaining"] == 10
    assert {(e.audience, e.payload["type"]) for e in events} >= {("team", "cooldown"), ("teacher", "cooldown")}


async def test_scenario_2_rejected_without_rank():
    engine = await running(k=1, n=10)
    await engine.submit(1, 1, "Q5", ans(5, "a"))
    with pytest.raises(SubmissionRejected) as e:
        await engine.submit(1, 1, "Q6", ans(6, "b"))
    assert e.value.reject_code is SubmissionRejectCode.COOLDOWN
    assert [s.unit_key for s in engine.submissions] == ["Q5"]


async def test_scenario_3_other_team_reaching_lead_also_cools_down():
    engine = await running(teams=3, k=2, n=10, units=None)
    clock = engine.clock
    await engine.submit(1, 1, "G1", ans(1, "a", 2, "b"))
    await engine.submit(1, 1, "G2", ans(3, "a", 4, "b"))  # 第1組 2 題 → 冷卻
    clock.advance(10)
    await engine.submit(2, 1, "Q5", ans(5, "x"))
    assert engine.view_for_team(2)["cooldown_remaining"] == 0  # 1 − 0 < 2
    await engine.submit(2, 1, "Q6", ans(6, "y"))  # 第2組 2 題、第3組 0 題 → 冷卻
    assert engine.view_for_team(2)["cooldown_remaining"] == 10
    assert engine.view_for_team(1)["cooldown_remaining"] == 0  # 第1組不受影響


async def test_scenario_4_others_catch_up_no_cooldown():
    engine = await running(teams=3, k=2, n=10)
    await engine.submit(1, 1, "Q5", ans(5, "a"))
    await engine.submit(2, 1, "Q6", ans(6, "b"))
    await engine.submit(3, 1, "G1", ans(1, "c", 2, "d"))
    await engine.submit(1, 1, "G2", ans(3, "e", 4, "f"))  # 第1組 2 題、最少 1 題 → 領先 1
    assert engine.view_for_team(1)["cooldown_remaining"] == 0


async def test_scenario_5_end_during_cooldown_rejects_as_not_running():
    engine = await running(k=1, n=10)
    await engine.submit(1, 1, "Q5", ans(5, "a"))
    await engine.end()
    with pytest.raises(SubmissionRejected) as e:
        await engine.submit(1, 1, "Q6", ans(6, "b"))
    assert e.value.reject_code is SubmissionRejectCode.NOT_RUNNING


async def test_single_team_never_cools_down():
    engine = await running(teams=1, k=1, n=10)
    for key, no in UNITS:
        await engine.submit(1, 1, key, ans(no, "a"))
    assert engine.view_for_team(1)["cooldown_remaining"] == 0


async def test_disabled_fairness_never_cools_down():
    engine = await running(fairness=False, k=1)
    for key, no in UNITS:
        await engine.submit(1, 1, key, ans(no, "a"))
    assert engine.view_for_team(1)["cooldown_remaining"] == 0


async def test_group_counts_as_one_win():
    engine = await running(k=2, n=10)
    await engine.submit(1, 1, "G1", ans(1, "a", 2, "b"))  # 題組 2 題只算 1
    assert engine.view_for_team(1)["cooldown_remaining"] == 0


async def test_cooldown_boundary_with_fake_clock():
    clock = FakeClock()
    engine = await running(clock=clock, k=1, n=10)
    await engine.submit(1, 1, "Q5", ans(5, "a"))
    clock.advance(9.9)
    with pytest.raises(SubmissionRejected) as e:
        await engine.submit(1, 1, "Q6", ans(6, "b"))
    assert e.value.extra["retry_after_seconds"] == 1
    clock.advance(0.1)
    r, _ = await engine.submit(1, 1, "Q6", ans(6, "b"))
    assert r["outcome"] == "success"

