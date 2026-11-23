"""公平機制：領先 K 題就冷卻 N 秒（spec FR-018、research R5 第 8 步）。純函式。"""

import math


def should_cooldown(team_wins: int, min_wins: int, cooldown_lead: int, fairness_enabled: bool) -> bool:
    """參數對應 data-model.md Activity.cooldown_lead、Activity.fairness_enabled。"""
    return fairness_enabled and team_wins - min_wins >= cooldown_lead


def remaining(until_monotonic: float, now: float) -> int:
    """剩餘秒數（無條件進位）；已到期回傳 0。參數對應 data-model.md Cooldown.until_monotonic。"""
    return max(0, math.ceil(until_monotonic - now))
