"""目前的活動與已載入的引擎（research R7、R9）：同一時間最多只有一場準備中或搶答中的活動。"""

from __future__ import annotations

import logging
from uuid import UUID, uuid4

from guided_buzz.activity import codes
from guided_buzz.activity.engine import ActivityEngine
from guided_buzz.activity.state import ActivityInfo, Clock, TeamState
from guided_buzz.activity.units import build_units
from guided_buzz.config import Settings
from guided_buzz.domain.errors import ActivityInProgress, InvalidInput, InvalidState
from guided_buzz.domain.models import ActivityPhase, WorksheetStatus
from guided_buzz.storage import worksheets
from guided_buzz.storage.activities import SqliteActivityRepository
from guided_buzz.storage.db import Database

log = logging.getLogger(__name__)

LIVE = (ActivityPhase.PREPARING, ActivityPhase.RUNNING)


class ActivityRegistry:
    def __init__(self, db: Database, settings: Settings, clock: Clock | None = None):
        self.db = db
        self.settings = settings
        self.repo = SqliteActivityRepository(db)
        self.clock = clock or Clock()
        self._engines: dict[UUID, ActivityEngine] = {}
        self._latest: UUID | None = None

    def startup(self) -> None:
        count = self.repo.mark_unfinished_interrupted()
        if count:
            log.info("伺服器啟動：%d 場未結束的活動已標示為已中斷", count)

    @property
    def latest(self) -> ActivityEngine | None:
        """本次啟動後最近建立的活動（老師主控台顯示用，結束後仍可檢視結果）。"""
        return self._engines.get(self._latest) if self._latest else None

    @property
    def current(self) -> ActivityEngine | None:
        return next((e for e in self._engines.values() if e.phase in LIVE), None)

    def _validate_teams(self, names: list[str]) -> list[str]:
        cleaned = [n.strip() for n in names]
        if not 1 <= len(cleaned) <= self.settings.max_teams:
            raise InvalidInput(f"組數必須是 1–{self.settings.max_teams} 組。")
        for i, name in enumerate(cleaned, 1):
            if not name:
                raise InvalidInput(f"第 {i} 組的組名不可為空白。")
            if len(name) > self.settings.team_name_max:
                raise InvalidInput(f"第 {i} 組的組名超過 {self.settings.team_name_max} 字。")
        dupes = sorted({n for n in cleaned if cleaned.count(n) > 1})
        if dupes:
            raise InvalidInput("組名不可重複：" + "、".join(dupes))
        return cleaned

    def create(self, owner: str, worksheet_id: str, team_names: list[str], fairness_enabled: bool | None, cooldown_seconds: int | None, cooldown_lead: int | None) -> ActivityEngine:
        if self.current is not None:
            raise ActivityInProgress()
        ws = worksheets.get(self.db, worksheet_id, owner)
        if ws.status is not WorksheetStatus.CONFIRMED:
            raise InvalidState("學習單尚未確認，確認後才能建立搶答活動。")
        names = self._validate_teams(team_names)
        s = self.settings
        info = ActivityInfo(
            id=uuid4(),
            worksheet_id=ws.id,
            owner=owner,
            phase=ActivityPhase.PREPARING,
            fairness_enabled=s.fairness_enabled if fairness_enabled is None else fairness_enabled,
            cooldown_seconds=cooldown_seconds or s.cooldown_seconds,
            cooldown_lead=cooldown_lead or s.cooldown_lead,
            created_at=self.clock.now(),
        )
        used: set[str] = set()
        teams = []
        for i, name in enumerate(names, 1):
            code = codes.new_code(used)
            used.add(code)
            teams.append(TeamState(i, name, codes.code_hash(code), 1, code))
        self.repo.create_activity(info, teams)
        engine = ActivityEngine(info, build_units(ws.parsed), {t.id: t for t in teams}, self.repo, s.max_answer_length, self.clock)
        self._engines[info.id] = engine
        self._latest = info.id
        log.info("建立活動 %s：%d 組、%d 個搶答單位", info.id, len(teams), len(engine.units))
        return engine

    def get(self, activity_id: UUID | str, owner: str | None = None) -> ActivityEngine:
        """回傳記憶體中的引擎；已結束但不在記憶體中（例如伺服器重啟後）的活動從資料庫載入。"""
        info = self.repo.get_info(activity_id, owner)
        engine = self._engines.get(info.id)
        if engine is not None:
            return engine
        if info.phase is ActivityPhase.INTERRUPTED:
            raise InvalidState("活動已中斷（伺服器曾重新啟動），請老師重新建立活動。")
        if info.phase is not ActivityPhase.ENDED:  # 資料庫中是進行中，但記憶體沒有：不應發生，視同中斷
            raise InvalidState("活動已中斷，請老師重新建立活動。")
        ws = worksheets.get(self.db, info.worksheet_id, info.owner)
        teams = self.repo.load_teams(info.id)
        engine = ActivityEngine(info, build_units(ws.parsed), {t.id: t for t in teams}, self.repo, self.settings.max_answer_length, self.clock, submissions=self.repo.load_submissions(info.id))
        self._engines[info.id] = engine
        return engine

    def phase_of(self, activity_id: UUID | str) -> ActivityPhase:
        info = self.repo.get_info(activity_id)
        engine = self._engines.get(info.id)
        return engine.phase if engine else info.phase

    def find_team_by_code(self, code: str) -> tuple[ActivityEngine, TeamState] | None:
        engine = self.current
        if engine is None:
            return None
        team = engine.find_team_by_code(code)
        return (engine, team) if team else None
