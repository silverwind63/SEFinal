"""從已保存的搶答活動組出 ActivityResult（001 contracts/results-provider.md、002 tasks T057）。"""

from uuid import UUID

from guided_buzz.domain.errors import NotFound
from guided_buzz.domain.models import ActivityPhase, ActivityResult, SubmissionRecord
from guided_buzz.storage.activities import SqliteActivityRepository


class SqliteActivityResultsProvider:
    def __init__(self, repo: SqliteActivityRepository):
        self._repo = repo

    def get_result(self, activity_id: UUID | str, requester: str) -> ActivityResult:
        info = self._repo.get_info(activity_id, requester)  # 不存在或不是活動老師 → NotFound
        if info.phase is not ActivityPhase.ENDED:
            return ActivityResult(info.id, info.worksheet_id, info.owner, False, ())
        names = {t.id: t.name for t in self._repo.load_teams(info.id)}
        records = [
            SubmissionRecord(
                question_nos=tuple(sorted(s.answers)),  # 答案的題號即搶答單位的題號（BuzzUnit.question_nos）
                team_name=names[s.team_id],
                answers=dict(s.answers),
                rank=s.rank,
                outcome=s.outcome,
            )
            for s in self._repo.load_submissions(info.id)
        ]
        if any(not r.question_nos for r in records):
            raise NotFound("搶答紀錄不完整，找不到這場活動的結果。")
        records.sort(key=lambda r: (r.question_nos[0], r.rank))
        return ActivityResult(info.id, info.worksheet_id, info.owner, True, tuple(records))
