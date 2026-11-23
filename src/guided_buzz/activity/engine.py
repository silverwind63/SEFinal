"""ActivityEngine：一場活動的判定核心（research R1、R5、R6、R7）。

所有會改變狀態的操作都在同一把 asyncio.Lock 內依序執行，「伺服器處理順序」就是取得鎖的順序。
引擎不處理 HTTP 或 WebSocket，只回傳結果與事件清單；推播由 realtime 在鎖釋放後送出。
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Protocol
from uuid import UUID

from guided_buzz.activity import codes, fairness
from guided_buzz.activity.state import ActivityInfo, Clock, Cooldown, Submission, TeamState, UnitStatus, team_wins, unit_status
from guided_buzz.domain.errors import InvalidState, NotEnded, NotFound, PersistFailed, SubmissionRejectCode, SubmissionRejected
from guided_buzz.domain.models import ActivityPhase, BuzzUnit, SubmissionOutcome

log = logging.getLogger(__name__)


class ActivityRepository(Protocol):
    def update_phase(self, activity_id: UUID, phase: ActivityPhase, *, started_at=None, ended_at=None) -> None: ...

    def persist_results(self, activity_id: UUID, submissions: list[Submission], ended_at) -> None: ...

    def update_invalidation(self, activity_id: UUID, invalidated_id: int, invalidated_at, promoted_id: int | None) -> None: ...

    def update_team_code(self, activity_id: UUID, team_id: int, code_hash: str, code_version: int) -> None: ...


@dataclass(frozen=True)
class Event:
    """audience：teacher（老師）、team（team_id 那一組）、all（所有連線）、revoke（撤銷 team_id 那一組的連線）。
    payload 為 {"type": "snapshot"} 時，推播中心會依每條連線的身分各自產生快照。"""

    audience: str
    payload: dict
    team_id: int | None = None


SNAPSHOT = {"type": "snapshot"}


@dataclass
class ActivityEngine:
    info: ActivityInfo
    units: list[BuzzUnit]
    teams: dict[int, TeamState]
    repo: ActivityRepository
    max_answer_length: int
    clock: Clock = field(default_factory=Clock)
    submissions: list[Submission] = field(default_factory=list)
    cooldowns: dict[int, Cooldown] = field(default_factory=dict)

    def __post_init__(self):
        self._lock = asyncio.Lock()
        self._units = {u.key: u for u in self.units}

    @property
    def id(self) -> UUID:
        return self.info.id

    @property
    def phase(self) -> ActivityPhase:
        return self.info.phase

    def _unit_subs(self, key: str) -> list[Submission]:
        return sorted((s for s in self.submissions if s.unit_key == key), key=lambda s: s.rank)

    def _wins(self) -> dict[int, int]:
        return team_wins(self.submissions, list(self.teams))

    def _cooldown_remaining(self, team_id: int) -> int:
        cd = self.cooldowns.get(team_id)
        if cd is None:
            return 0
        left = fairness.remaining(cd.until_monotonic, self.clock.monotonic())
        if left == 0:
            del self.cooldowns[team_id]
        return left

    # ---------- 階段 ----------

    async def start(self) -> list[Event]:
        async with self._lock:
            if self.phase is not ActivityPhase.PREPARING:
                raise InvalidState("只有準備中的活動可以開始搶答。")
            if not self.units or not self.teams:
                raise InvalidState("至少需要 1 個搶答單位與 1 個組別才能開始。")
            now = self.clock.now()
            self.repo.update_phase(self.id, ActivityPhase.RUNNING, started_at=now)
            self.info.phase, self.info.started_at = ActivityPhase.RUNNING, now
            log.info("活動 %s 開始搶答", self.id)
            return [Event("all", {"type": "phase_changed", "phase": ActivityPhase.RUNNING.value})]

    async def end(self) -> list[Event]:
        async with self._lock:
            if self.phase is not ActivityPhase.RUNNING:
                raise InvalidState("只有搶答中的活動可以結束。")
            now = self.clock.now()
            try:
                self.repo.persist_results(self.id, self.submissions, now)  # 寫入成功後才改變階段（FR-026）
            except Exception as e:
                log.error("活動 %s 結果保存失敗：%s", self.id, type(e).__name__)
                raise PersistFailed() from None
            self.info.phase, self.info.ended_at = ActivityPhase.ENDED, now
            self.cooldowns.clear()
            log.info("活動 %s 已結束，共 %d 筆送出", self.id, len(self.submissions))
            return [Event("all", {"type": "phase_changed", "phase": ActivityPhase.ENDED.value}), Event("all", SNAPSHOT)]

    # ---------- 送出（research R5） ----------

    async def submit(self, team_id: int, code_version: int, unit_key: str, answers: dict[int, str]) -> tuple[dict, list[Event]]:
        async with self._lock:
            if self.phase is not ActivityPhase.RUNNING:  # 1
                raise SubmissionRejected(SubmissionRejectCode.NOT_RUNNING)
            team = self.teams.get(team_id)
            if team is None or team.code_version != code_version:  # 2
                raise SubmissionRejected(SubmissionRejectCode.UNAUTHORIZED)
            left = self._cooldown_remaining(team_id)  # 3：被拒的送出不記錄、不佔順位
            if left:
                raise SubmissionRejected(SubmissionRejectCode.COOLDOWN, seconds=left)
            unit = self._units.get(unit_key)  # 4
            if unit is None:
                raise SubmissionRejected(SubmissionRejectCode.UNKNOWN_UNIT)
            expected, given = set(unit.question_nos), set(answers)
            if expected != given:
                raise SubmissionRejected(SubmissionRejectCode.INCOMPLETE_GROUP, missing=sorted(expected - given), unexpected=sorted(given - expected))
            cleaned: dict[int, str] = {}
            for no in unit.question_nos:  # 5
                text = answers[no].strip()
                if not text:
                    raise SubmissionRejected(SubmissionRejectCode.INVALID_ANSWER, question_no=no, reason="不可為空白")
                if len(text) > self.max_answer_length:
                    raise SubmissionRejected(SubmissionRejectCode.INVALID_ANSWER, question_no=no, reason=f"超過 {self.max_answer_length} 字")
                cleaned[no] = text
            existing = self._unit_subs(unit_key)
            if any(s.team_id == team_id for s in existing):  # 6
                raise SubmissionRejected(SubmissionRejectCode.ALREADY_SUBMITTED)
            won = any(s.outcome is SubmissionOutcome.SUCCESS for s in existing)  # 7
            sub = Submission(
                id=len(self.submissions) + 1,
                unit_key=unit_key,
                team_id=team_id,
                answers=cleaned,
                rank=len(existing) + 1,
                outcome=SubmissionOutcome.NOT_WON if won else SubmissionOutcome.SUCCESS,
                received_at=self.clock.now(),
            )
            self.submissions.append(sub)
            events = [
                Event("team", {"type": "team_submission", "unit_key": unit_key, "rank": sub.rank, "outcome": sub.outcome.value}, team_id),
                Event("teacher", {"type": "submission", "unit_key": unit_key, "team_id": team_id, "answers": {str(k): v for k, v in cleaned.items()}, "rank": sub.rank, "outcome": sub.outcome.value}),
            ]
            if sub.outcome is SubmissionOutcome.SUCCESS:  # 8
                events += self._maybe_cooldown(team_id, sub.id)
            message = "搶答成功！" if sub.outcome is SubmissionOutcome.SUCCESS else f"未搶到，第 {sub.rank} 順位"
            return {"unit_key": unit_key, "rank": sub.rank, "outcome": sub.outcome.value, "message": message}, events

    def _maybe_cooldown(self, team_id: int, trigger_id: int) -> list[Event]:
        wins = self._wins()
        if not fairness.should_cooldown(wins[team_id], min(wins.values()), self.info.cooldown_lead, self.info.fairness_enabled):
            return []
        n = self.info.cooldown_seconds
        self.cooldowns[team_id] = Cooldown(team_id, self.clock.monotonic() + n, self.clock.now() + timedelta(seconds=n), trigger_id)
        return self._cooldown_events(team_id, True, n)

    def _cooldown_events(self, team_id: int, active: bool, seconds: int) -> list[Event]:
        payload = {"type": "cooldown", "team_id": team_id, "active": active, "remaining_seconds": seconds}
        return [Event("team", payload, team_id), Event("teacher", payload)]

    # ---------- 判定無效與遞補（research R6） ----------

    async def invalidate(self, unit_key: str) -> tuple[dict, list[Event]]:
        async with self._lock:
            if self.phase not in (ActivityPhase.RUNNING, ActivityPhase.ENDED):
                raise InvalidState("只有搶答中或已結束的活動可以判定無效。")
            unit = self._units.get(unit_key)
            if unit is None:
                raise NotFound("找不到這個搶答單位。")
            subs = self._unit_subs(unit_key)
            winner = next((s for s in subs if s.outcome is SubmissionOutcome.SUCCESS), None)
            if winner is None:
                raise InvalidState("這個搶答單位目前沒有成功者，無法判定無效。")
            successor = next((s for s in subs if s.outcome is SubmissionOutcome.NOT_WON), None)
            now = self.clock.now()
            if self.phase is ActivityPhase.ENDED:
                self.repo.update_invalidation(self.id, winner.id, now, successor.id if successor else None)
            winner.outcome, winner.invalidated_at = SubmissionOutcome.INVALIDATED, now
            if successor:
                successor.outcome = SubmissionOutcome.SUCCESS  # 遞補成功不觸發冷卻
            events = [
                Event("team", {"type": "invalidated", "unit_key": unit_key, "message": f"{unit.display}的答案已被老師判定無效"}, winner.team_id),
                Event("teacher", {"type": "invalidated", "unit_key": unit_key, "team_id": winner.team_id}),
            ]
            if successor:
                events += [
                    Event("team", {"type": "promoted", "unit_key": unit_key, "message": f"{unit.display}遞補為搶答成功"}, successor.team_id),
                    Event("teacher", {"type": "promoted", "unit_key": unit_key, "team_id": successor.team_id}),
                ]
            cd = self.cooldowns.get(winner.team_id)
            if cd and cd.trigger_submission_id == winner.id:
                del self.cooldowns[winner.team_id]
                events += self._cooldown_events(winner.team_id, False, 0)
            status = unit_status(self._unit_subs(unit_key), self.phase)
            log.info("活動 %s 的單位 %s 判定無效（遞補：%s）", self.id, unit_key, "有" if successor else "無")
            result = {
                "unit_key": unit_key,
                "invalidated_team_id": winner.team_id,
                "promoted_team_id": successor.team_id if successor else None,
                "unit_status": status.value,
            }
            return result, events

    # ---------- 組別代碼 ----------

    async def regenerate_code(self, team_id: int) -> tuple[str, list[Event]]:
        async with self._lock:
            if self.phase not in (ActivityPhase.PREPARING, ActivityPhase.RUNNING):
                raise InvalidState("活動已結束或已中斷，不能重新產生代碼。")
            team = self.teams.get(team_id)
            if team is None:
                raise NotFound("找不到這個組別。")
            code = codes.new_code({t.code for t in self.teams.values() if t.code})
            self.repo.update_team_code(self.id, team_id, codes.code_hash(code), team.code_version + 1)
            team.code, team.code_hash, team.code_version = code, codes.code_hash(code), team.code_version + 1
            log.info("活動 %s 的組別 %d 重新產生代碼", self.id, team_id)
            return code, [Event("revoke", {"type": "session_revoked", "reason": "code_regenerated"}, team_id)]

    def find_team_by_code(self, code: str) -> TeamState | None:
        digest = codes.code_hash(code)
        return next((t for t in self.teams.values() if t.code_hash == digest), None)

    # ---------- 檢視（依身分過濾，FR-014、FR-015、FR-016） ----------

    def _team_name(self, team_id: int) -> str:
        return self.teams[team_id].name

    def _sub_out(self, s: Submission) -> dict:
        return {
            "id": s.id,
            "team_id": s.team_id,
            "team_name": self._team_name(s.team_id),
            "answers": {str(k): v for k, v in s.answers.items()},
            "rank": s.rank,
            "outcome": s.outcome.value,
        }

    def _unit_list(self) -> list[dict]:
        return [{"key": u.key, "display": u.display, "question_nos": list(u.question_nos)} for u in self.units]

    def view_for_teacher(self) -> dict:
        wins = self._wins()
        show_codes = self.phase in (ActivityPhase.PREPARING, ActivityPhase.RUNNING)
        return {
            "id": str(self.id),
            "worksheet_id": str(self.info.worksheet_id),
            "phase": self.phase.value,
            "fairness": {"enabled": self.info.fairness_enabled, "cooldown_seconds": self.info.cooldown_seconds, "cooldown_lead": self.info.cooldown_lead},
            "teams": [
                {"id": t.id, "name": t.name, "code": t.code if show_codes else None, "wins": wins[t.id], "cooldown_remaining": self._cooldown_remaining(t.id)}
                for t in self.teams.values()
            ],
            "units": [
                {**u, "status": unit_status(self._unit_subs(u["key"]), self.phase).value, "submissions": [self._sub_out(s) for s in self._unit_subs(u["key"])]}
                for u in self._unit_list()
            ],
        }

    def view_for_team(self, team_id: int) -> dict:
        """搶答中只含本組資料與單位清單（不含任何單位狀態）；結束後另含完整結果。"""
        team = self.teams[team_id]
        mine = [
            {"unit_key": s.unit_key, "rank": s.rank, "outcome": s.outcome.value, "answers": {str(k): v for k, v in s.answers.items()}}
            for s in self.submissions
            if s.team_id == team_id
        ]
        return {
            "activity_id": str(self.id),
            "phase": self.phase.value,
            "team": {"id": team.id, "name": team.name},
            "cooldown_remaining": self._cooldown_remaining(team_id),
            "units": self._unit_list(),
            "my_submissions": mine,
            "results": self.results_view(include_all=False) if self.phase is ActivityPhase.ENDED else None,
        }

    def results_view(self, include_all: bool) -> dict:
        if self.phase is not ActivityPhase.ENDED:
            raise NotEnded()
        wins = self._wins()
        units = []
        for u in self._unit_list():
            subs = self._unit_subs(u["key"])
            winner = next((s for s in subs if s.outcome is SubmissionOutcome.SUCCESS), None)
            entry = {
                **u,
                "status": (UnitStatus.WON if winner else UnitStatus.NO_WINNER).value,
                "winner": {"team_id": winner.team_id, "team_name": self._team_name(winner.team_id), "answers": {str(k): v for k, v in winner.answers.items()}} if winner else None,
            }
            if include_all:
                entry["submissions"] = [self._sub_out(s) for s in subs]
            units.append(entry)
        return {"activity_id": str(self.id), "units": units, "teams": [{"id": t.id, "name": t.name, "wins": wins[t.id]} for t in self.teams.values()]}
