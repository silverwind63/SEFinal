"""判定引擎內部狀態（data-model.md Team、Submission、Cooldown）。只給 activity 套件使用。"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from uuid import UUID

from guided_buzz.domain.models import ActivityPhase, SubmissionOutcome


class Clock:
    """伺服器時鐘；測試時以假時鐘替換（research R5「時間」）。"""

    def monotonic(self) -> float:
        return time.monotonic()

    def now(self) -> datetime:
        return datetime.now(timezone.utc)


@dataclass
class ActivityInfo:
    id: UUID
    worksheet_id: UUID
    owner: str
    phase: ActivityPhase
    fairness_enabled: bool
    cooldown_seconds: int
    cooldown_lead: int
    created_at: datetime
    started_at: datetime | None = None
    ended_at: datetime | None = None


@dataclass
class TeamState:
    id: int
    name: str
    code_hash: str
    code_version: int = 1
    code: str | None = field(default=None, repr=False)  # 明文只在記憶體，供老師畫面顯示


@dataclass
class Submission:
    id: int
    unit_key: str
    team_id: int
    answers: dict[int, str]
    rank: int
    outcome: SubmissionOutcome
    received_at: datetime
    invalidated_at: datetime | None = None


@dataclass
class Cooldown:
    team_id: int
    until_monotonic: float
    until_utc: datetime
    trigger_submission_id: int


class UnitStatus(str, Enum):
    NO_SUBMISSION = "no_submission"  # 尚無人搶答
    WON = "won"  # 已搶答
    OPEN = "open"  # 有送出但成功者已被判無效（搶答中）
    NO_WINNER = "no_winner"  # 無人搶答（已結束）


def unit_status(submissions: list[Submission], phase: ActivityPhase) -> UnitStatus:
    if any(s.outcome is SubmissionOutcome.SUCCESS for s in submissions):
        return UnitStatus.WON
    if phase is ActivityPhase.ENDED:
        return UnitStatus.NO_WINNER
    return UnitStatus.OPEN if submissions else UnitStatus.NO_SUBMISSION


def team_wins(submissions: list[Submission], team_ids: list[int]) -> dict[int, int]:
    wins = {t: 0 for t in team_ids}
    for s in submissions:
        if s.outcome is SubmissionOutcome.SUCCESS:
            wins[s.team_id] += 1
    return wins
