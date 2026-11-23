"""學生 Session 與輸錯限制（tasks T013）。"""

from uuid import uuid4

import pytest

from guided_buzz.auth.sessions import StudentSessions
from guided_buzz.domain.errors import TooManyAttempts


class Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


@pytest.fixture
def clock():
    return Clock()


def make(clock, failures=5, lock=60, global_limit=60):
    return StudentSessions(failures, lock, global_limit, monotonic=clock)


def test_issue_and_get_and_revoke(clock):
    s = make(clock)
    aid = uuid4()
    a1 = s.issue(aid, 1, 1)
    a2 = s.issue(aid, 1, 1)
    b = s.issue(aid, 2, 1)
    assert s.get(a1.token).team_id == 1 and a1.token != a2.token
    s.revoke_team(aid, 1)
    assert s.get(a1.token) is None and s.get(a2.token) is None
    assert s.get(b.token) is not None


def test_teacher_token_is_not_a_student_session(clock):
    assert make(clock).get("some-teacher-token") is None


def test_window_locked_after_max_failures_other_window_unaffected(clock):
    s = make(clock, failures=5, lock=60)
    for _ in range(5):
        s.check_allowed("w1")
        s.record_failure("w1")
    with pytest.raises(TooManyAttempts) as e:
        s.check_allowed("w1")
    assert e.value.extra["retry_after_seconds"] == 60
    s.check_allowed("w2")  # 另一個視窗不受影響


def test_lock_expires(clock):
    s = make(clock, failures=2, lock=30)
    s.record_failure("w1")
    s.record_failure("w1")
    clock.t += 29.5
    with pytest.raises(TooManyAttempts):
        s.check_allowed("w1")
    clock.t += 0.5
    s.check_allowed("w1")


def test_four_failures_then_success_resets(clock):
    s = make(clock, failures=5)
    for _ in range(4):
        s.record_failure("w1")
    s.record_success("w1")
    for _ in range(4):
        s.record_failure("w1")
    s.check_allowed("w1")


def test_global_limit_blocks_every_window_until_minute_passes(clock):
    s = make(clock, failures=100, global_limit=3)
    for i in range(3):
        s.record_failure(f"w{i}")
    with pytest.raises(TooManyAttempts) as e:
        s.check_allowed("brand-new-window")
    assert e.value.extra["retry_after_seconds"] == 60
    clock.t += 60
    s.check_allowed("brand-new-window")
