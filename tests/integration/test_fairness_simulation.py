"""公平機制模擬（tasks T053、SC-006）：一組反應最快時，啟用公平機制能讓更多組至少成功一題。"""

import random

from guided_buzz.domain.errors import SubmissionRejected
from guided_buzz.domain.models import BuzzUnit
from tests.buzz import ans, running

TEAMS = 6
UNITS = [BuzzUnit(f"Q{n}", (n,), f"第 {n} 題") for n in range(1, 13)]


async def simulate(fairness_enabled: bool, seed: int = 20261123) -> int:
    """每一輪：第 1 組最快，其他組依隨機順序；被冷卻的組會跳過這一輪。回傳至少成功一題的組數。"""
    rng = random.Random(seed)
    engine = await running(teams=TEAMS, units=UNITS, fairness=fairness_enabled, k=1, n=30)
    for unit in UNITS:
        order = [1] + rng.sample(range(2, TEAMS + 1), TEAMS - 1)
        for team in order:
            try:
                await engine.submit(team, 1, unit.key, ans(unit.question_nos[0], f"t{team}"))
            except SubmissionRejected:
                continue
        engine.clock.advance(5)  # 每題約 5 秒
    return sum(1 for t in engine.view_for_teacher()["teams"] if t["wins"] > 0)


async def test_fairness_spreads_wins():
    with_fairness, without = await simulate(True), await simulate(False)
    assert without == 1  # 沒有公平機制時，最快的組包辦全部
    assert with_fairness > without
