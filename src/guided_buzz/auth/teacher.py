"""老師登入、Token 簽發與驗證、錯誤次數限制（research R9）。"""

import hmac
import logging
import secrets
import time

from guided_buzz.domain.errors import InvalidCredentials, LoginLocked

log = logging.getLogger(__name__)

OWNER = "teacher"


class TeacherAuth:
    def __init__(self, password: str, token_ttl: int, max_failures: int, lock_seconds: int):
        self._password = password
        self._ttl = token_ttl
        self._max_failures = max_failures
        self._lock_seconds = lock_seconds
        self._tokens: dict[str, float] = {}
        self._failures = 0
        self._locked_until = 0.0

    def login(self, password: str) -> str:
        now = time.monotonic()
        if now < self._locked_until:
            raise LoginLocked(int(self._locked_until - now) + 1)
        if not hmac.compare_digest(password.encode(), self._password.encode()):
            self._failures += 1
            if self._failures >= self._max_failures:
                self._failures = 0
                self._locked_until = now + self._lock_seconds
            log.info("老師登入失敗")
            raise InvalidCredentials()
        self._failures = 0
        token = secrets.token_urlsafe(32)
        self._tokens[token] = now + self._ttl
        log.info("老師登入成功")
        return token

    def verify(self, token: str) -> str | None:
        expires = self._tokens.get(token)
        if expires is None:
            return None
        if time.monotonic() >= expires:
            del self._tokens[token]
            return None
        return OWNER
