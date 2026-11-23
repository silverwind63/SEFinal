"""搶答活動 repository（data-model.md Activity、Team、Submission）。資料表只由 storage 模組存取。

進行中的送出只存在記憶體；活動結束時才以一筆交易寫入（research R7）。
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from guided_buzz.activity.state import ActivityInfo, Submission, TeamState
from guided_buzz.domain.errors import NotFound
from guided_buzz.domain.models import ActivityPhase, SubmissionOutcome
from guided_buzz.storage.db import Database

NOT_FOUND_MESSAGE = "找不到這場活動。"


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt else None


def _dt(text: str | None) -> datetime | None:
    return datetime.fromisoformat(text) if text else None


def _uuid(value: UUID | str) -> str:
    try:
        return str(UUID(str(value)))
    except ValueError:
        raise NotFound(NOT_FOUND_MESSAGE) from None


def _info(row) -> ActivityInfo:
    return ActivityInfo(
        id=UUID(row["id"]),
        worksheet_id=UUID(row["worksheet_id"]),
        owner=row["owner"],
        phase=ActivityPhase(row["phase"]),
        fairness_enabled=bool(row["fairness_enabled"]),
        cooldown_seconds=row["cooldown_seconds"],
        cooldown_lead=row["cooldown_lead"],
        created_at=_dt(row["created_at"]),
        started_at=_dt(row["started_at"]),
        ended_at=_dt(row["ended_at"]),
    )


class SqliteActivityRepository:
    def __init__(self, db: Database):
        self.db = db

    # ---- 建立與查詢 ----

    def create_activity(self, info: ActivityInfo, teams: list[TeamState]) -> None:
        """寫入 Activity 與 Team；Team.code 明文不寫入資料庫，只存 Team.code_hash。"""
        with self.db.transaction() as conn:
            conn.execute(
                "INSERT INTO activities VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL)",
                (str(info.id), str(info.worksheet_id), info.owner, info.phase.value, int(info.fairness_enabled), info.cooldown_seconds, info.cooldown_lead, _iso(info.created_at)),
            )
            conn.executemany("INSERT INTO teams VALUES (?, ?, ?, ?, ?)", [(str(info.id), t.id, t.name, t.code_hash, t.code_version) for t in teams])

    def get_info(self, activity_id: UUID | str, owner: str | None = None) -> ActivityInfo:
        """owner 不為 None 時，非擁有者視同不存在。"""
        aid = _uuid(activity_id)
        with self.db.transaction() as conn:
            row = conn.execute("SELECT * FROM activities WHERE id = ?", (aid,)).fetchone()
        if row is None or (owner is not None and row["owner"] != owner):
            raise NotFound(NOT_FOUND_MESSAGE)
        return _info(row)

    def list_by_owner(self, owner: str) -> list[ActivityInfo]:
        with self.db.transaction() as conn:
            rows = conn.execute("SELECT * FROM activities WHERE owner = ? ORDER BY created_at DESC", (owner,)).fetchall()
        return [_info(r) for r in rows]

    def load_teams(self, activity_id: UUID) -> list[TeamState]:
        with self.db.transaction() as conn:
            rows = conn.execute("SELECT * FROM teams WHERE activity_id = ? ORDER BY team_id", (str(activity_id),)).fetchall()
        return [TeamState(r["team_id"], r["name"], r["code_hash"], r["code_version"]) for r in rows]

    def load_submissions(self, activity_id: UUID) -> list[Submission]:
        aid = str(activity_id)
        with self.db.transaction() as conn:
            rows = conn.execute("SELECT * FROM submissions WHERE activity_id = ? ORDER BY id", (aid,)).fetchall()
            answers = conn.execute("SELECT * FROM submission_answers WHERE activity_id = ?", (aid,)).fetchall()
        by_sub: dict[int, dict[int, str]] = {}
        for a in answers:
            by_sub.setdefault(a["submission_id"], {})[a["question_no"]] = a["answer"]
        return [
            Submission(r["id"], r["unit_key"], r["team_id"], dict(sorted(by_sub.get(r["id"], {}).items())), r["rank"], SubmissionOutcome(r["outcome"]), _dt(r["received_at"]), _dt(r["invalidated_at"]))
            for r in rows
        ]

    def mark_unfinished_interrupted(self) -> int:
        """伺服器啟動時：準備中、搶答中的活動一律作廢（FR-027）。"""
        with self.db.transaction() as conn:
            cur = conn.execute(
                "UPDATE activities SET phase = ? WHERE phase IN (?, ?)",
                (ActivityPhase.INTERRUPTED.value, ActivityPhase.PREPARING.value, ActivityPhase.RUNNING.value),
            )
            return cur.rowcount

    # ---- ActivityRepository（engine 使用） ----

    def update_phase(self, activity_id: UUID, phase: ActivityPhase, *, started_at=None, ended_at=None) -> None:
        with self.db.transaction() as conn:
            conn.execute(
                "UPDATE activities SET phase = ?, started_at = COALESCE(?, started_at), ended_at = COALESCE(?, ended_at) WHERE id = ?",
                (phase.value, _iso(started_at), _iso(ended_at), str(activity_id)),
            )

    def persist_results(self, activity_id: UUID, submissions: list[Submission], ended_at) -> None:
        """一筆交易寫入所有送出（Submission.rank、Submission.outcome、Submission.answers），並把階段設為已結束。"""
        aid = str(activity_id)
        with self.db.transaction() as conn:
            conn.executemany(
                "INSERT INTO submissions VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                [(aid, s.id, s.unit_key, s.team_id, s.rank, s.outcome.value, _iso(s.received_at), _iso(s.invalidated_at)) for s in submissions],
            )
            conn.executemany(
                "INSERT INTO submission_answers VALUES (?, ?, ?, ?)",
                [(aid, s.id, no, text) for s in submissions for no, text in s.answers.items()],
            )
            conn.execute("UPDATE activities SET phase = ?, ended_at = ? WHERE id = ?", (ActivityPhase.ENDED.value, _iso(ended_at), aid))

    def update_invalidation(self, activity_id: UUID, invalidated_id: int, invalidated_at, promoted_id: int | None) -> None:
        aid = str(activity_id)
        with self.db.transaction() as conn:
            conn.execute(
                "UPDATE submissions SET outcome = ?, invalidated_at = ? WHERE activity_id = ? AND id = ?",
                (SubmissionOutcome.INVALIDATED.value, _iso(invalidated_at), aid, invalidated_id),
            )
            if promoted_id is not None:
                conn.execute("UPDATE submissions SET outcome = ? WHERE activity_id = ? AND id = ?", (SubmissionOutcome.SUCCESS.value, aid, promoted_id))

    def update_team_code(self, activity_id: UUID, team_id: int, code_hash: str, code_version: int) -> None:
        with self.db.transaction() as conn:
            conn.execute("UPDATE teams SET code_hash = ?, code_version = ? WHERE activity_id = ? AND team_id = ?", (code_hash, code_version, str(activity_id), team_id))
