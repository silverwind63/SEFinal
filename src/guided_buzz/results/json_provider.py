"""從 JSON 結果檔讀取搶答結果（contracts/results-provider.md），供 002 完成前的測試與驗證使用。"""

import json
from pathlib import Path
from uuid import UUID

from guided_buzz.domain.errors import NotFound, ResultsFileInvalid
from guided_buzz.domain.models import ActivityResult, SubmissionOutcome, SubmissionRecord


class JsonFileResultsProvider:
    def __init__(self, results_dir: Path):
        self._dir = results_dir

    def get_result(self, activity_id: UUID | str, requester: str) -> ActivityResult:
        try:
            activity_uuid = UUID(str(activity_id))
        except ValueError:
            raise NotFound("找不到這場活動。") from None
        path = self._dir / f"{activity_uuid}.json"  # 只用合法 UUID 組路徑，避免路徑穿越
        if not path.is_file():
            raise NotFound("找不到這場活動。")
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            raise ResultsFileInvalid("搶答結果檔無法讀取或不是合法的 JSON。") from None
        if data.get("owner") != requester:
            raise NotFound("找不到這場活動。")
        records = []
        for i, raw in enumerate(data.get("submissions", []), 1):
            try:
                records.append(
                    SubmissionRecord(
                        question_nos=tuple(int(n) for n in raw["question_nos"]),
                        team_name=str(raw["team_name"]),
                        answers={int(k): str(v) for k, v in raw["answers"].items()},
                        rank=int(raw["rank"]),
                        outcome=SubmissionOutcome(raw["outcome"]),
                    )
                )
            except (KeyError, TypeError, ValueError) as e:
                raise ResultsFileInvalid(f"搶答結果檔第 {i} 筆紀錄格式錯誤：{e}") from None
        try:
            return ActivityResult(activity_uuid, UUID(str(data["worksheet_id"])), requester, bool(data.get("ended")), tuple(records))
        except (KeyError, ValueError) as e:
            raise ResultsFileInvalid(f"搶答結果檔格式錯誤：{e}") from None
