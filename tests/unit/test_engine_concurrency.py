"""同時送出（tasks T032、SC-002）：判定只依伺服器處理順序，每個單位恰好一個成功者。"""

import asyncio

import pytest

from guided_buzz.domain.errors import SubmissionRejectCode, SubmissionRejected
from tests.buzz import ans, running


async def gather_results(coros):
    return await asyncio.gather(*coros, return_exceptions=True)


async def test_five_teams_at_once_repeated_100_times():
    for _ in range(100):
        engine = await running(teams=5, fairness=False)
        results = await gather_results([engine.submit(t, 1, "Q5", ans(5, f"t{t}")) for t in range(1, 6)])
        outcomes = [r[0] for r in results]
        assert sum(o["outcome"] == "success" for o in outcomes) == 1
        assert sorted(o["rank"] for o in outcomes) == [1, 2, 3, 4, 5]


async def test_three_windows_of_same_team_only_one_accepted():
    engine = await running()
    results = await gather_results([engine.submit(1, 1, "Q5", ans(5, f"w{i}")) for i in range(3)])
    accepted = [r for r in results if not isinstance(r, Exception)]
    rejected = [r for r in results if isinstance(r, SubmissionRejected)]
    assert len(accepted) == 1 and len(rejected) == 2
    assert all(r.reject_code is SubmissionRejectCode.ALREADY_SUBMITTED for r in rejected)
    assert len(engine.submissions) == 1


async def test_submit_processed_after_end_is_rejected():
    engine = await running()
    results = await gather_results([engine.submit(1, 1, "Q5", ans(5, "a")), engine.end(), engine.submit(2, 1, "Q6", ans(6, "b"))])
    assert results[0][0]["outcome"] == "success"
    assert isinstance(results[2], SubmissionRejected) and results[2].reject_code is SubmissionRejectCode.NOT_RUNNING
    assert len(engine.submissions) == 1


async def test_invalidate_and_submit_at_once_keep_single_winner():
    engine = await running()
    await engine.submit(1, 1, "Q5", ans(5, "a"))
    await gather_results([engine.invalidate("Q5"), engine.submit(2, 1, "Q5", ans(5, "b"))])
    winners = [s for s in engine.submissions if s.outcome.value == "success"]
    assert len(winners) == 1 and winners[0].team_id == 2


@pytest.mark.parametrize("teams", [2, 6])
async def test_ranks_contiguous_for_many_units(teams):
    engine = await running(teams=teams, fairness=False)
    coros = [engine.submit(t, 1, u, ans(n, "x")) for t in range(1, teams + 1) for u, n in (("Q5", 5), ("Q6", 6))]
    await gather_results(coros)
    for key in ("Q5", "Q6"):
        ranks = sorted(s.rank for s in engine.submissions if s.unit_key == key)
        assert ranks == list(range(1, teams + 1))
