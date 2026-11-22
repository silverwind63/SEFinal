"""活動結果 CSV（research R7）：UTF-8 BOM、CRLF、依題號與順位排序，題組依填空拆列。"""

import csv
import io

from guided_buzz.domain.errors import ResultsFileInvalid
from guided_buzz.domain.models import ActivityResult, ParsedWorksheet, SubmissionOutcome

HEADER = ["題號", "組別", "答案", "搶答順位", "結果"]
OUTCOME_TEXT = {SubmissionOutcome.SUCCESS: "成功", SubmissionOutcome.NOT_WON: "未搶到", SubmissionOutcome.INVALIDATED: "無效"}


def to_csv(result: ActivityResult, parsed: ParsedWorksheet) -> tuple[str, int]:
    known = {b.question_no for b in parsed.questions}
    rows = []
    for i, record in enumerate(result.submissions, 1):
        for n in record.question_nos:
            if n not in known:
                raise ResultsFileInvalid(f"搶答結果第 {i} 筆紀錄的題號 {n} 不存在於學習單中。")
            rows.append((n, record.rank, record.team_name, record.answers[n], OUTCOME_TEXT[record.outcome]))
    rows.sort(key=lambda r: (r[0], r[1]))
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\r\n", quoting=csv.QUOTE_MINIMAL)
    writer.writerow(HEADER)
    writer.writerows([n, team, answer, rank, outcome] for n, rank, team, answer, outcome in rows)
    return "﻿" + buffer.getvalue(), len(rows)
