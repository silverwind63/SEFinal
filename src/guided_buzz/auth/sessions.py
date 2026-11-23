"""學生 Session 與加入時的輸錯限制（research R3、data-model.md Session）。

- 每個瀏覽器視窗各自持有 Token（前端存在 sessionStorage），所以同一瀏覽器的各視窗身分互不影響（FR-005a）。
- 輸錯次數以 X-Window-Id 計算，不以 IP 計算（所有視窗都在同一台電腦）；另設全體每分鐘上限。
- Token 與組別代碼一律不寫入 log。
"""

from __future__ import annotations

import logging
import math
import secrets
import time
from collections import deque
from dataclasses import dataclass
from typing import Callable
from uuid import UUID

from guided_buzz.domain.errors import TooManyAttempts

log = logging.getLogger(__name__)

GLOBAL_WINDOW_SECONDS = 60


@dataclass(frozen=True)
class StudentSession:
    """data-model.md Session.token、Session.role（team）、Session.activity_id、Session.team_id、Session.code_version。"""

    token: str
    activity_id: UUID
    team_id: int
    code_version: int
    role: str = "team"


@dataclass
class _WindowState:
    failures: int = 0
    locked_until: float = 0.0


class StudentSessions:
    def __init__(self, max_failures: int, lock_seconds: int, global_failures_per_min: int, monotonic: Callable[[], float] = time.monotonic):
        self._max_failures = max_failures
        self._lock_seconds = lock_seconds
        self._global_limit = global_failures_per_min
        self._now = monotonic
        self._sessions: dict[str, StudentSession] = {}
        self._windows: dict[str, _WindowState] = {}
        self._global_failures: deque[float] = deque()

    # ---- 輸錯限制 ----

    def check_allowed(self, window_id: str) -> None:
        """加入前呼叫：此視窗被鎖定，或全體輸錯超過上限時拋出 TooManyAttempts。"""
        now = self._now()
        state = self._windows.get(window_id)
        if state and now < state.locked_until:
            raise TooManyAttempts(math.ceil(state.locked_until - now))
        while self._global_failures and now - self._global_failures[0] >= GLOBAL_WINDOW_SECONDS:
            self._global_failures.popleft()
        if len(self._global_failures) >= self._global_limit:
            raise TooManyAttempts(math.ceil(GLOBAL_WINDOW_SECONDS - (now - self._global_failures[0])))

    def record_failure(self, window_id: str) -> None:
        now = self._now()
        self._global_failures.append(now)
        state = self._windows.setdefault(window_id, _WindowState())
        state.failures += 1
        if state.failures >= self._max_failures:
            state.failures = 0
            state.locked_until = now + self._lock_seconds
        log.info("輸入組別代碼失敗")

    def record_success(self, window_id: str) -> None:
        self._windows.pop(window_id, None)

    # ---- Session ----

    def issue(self, activity_id: UUID, team_id: int, code_version: int) -> StudentSession:
        session = StudentSession(secrets.token_urlsafe(32), activity_id, team_id, code_version)
        self._sessions[session.token] = session
        return session

    def get(self, token: str) -> StudentSession | None:
        return self._sessions.get(token)

    def revoke_team(self, activity_id: UUID, team_id: int) -> None:
        """代碼重新產生後，該組所有 Session 立即失效（FR-005b）。"""
        for token, s in list(self._sessions.items()):
            if s.activity_id == activity_id and s.team_id == team_id:
                del self._sessions[token]
