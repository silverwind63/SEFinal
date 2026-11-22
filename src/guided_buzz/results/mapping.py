"""把搶答結果對應到填空格（data-model.md SubmissionRecord、Blank.location）。"""

from guided_buzz.domain.errors import ResultsFileInvalid
from guided_buzz.domain.models import ActivityResult, CellRef, ParsedWorksheet, SubmissionOutcome


def success_answers(result: ActivityResult, parsed: ParsedWorksheet) -> tuple[dict[CellRef, str], tuple[int, ...], tuple[int, ...]]:
    """回傳（{填空格: 成功答案}, 有成功答案的題號, 沒有成功答案的題號）；只使用伺服器判定的 success（FR-018）。"""
    location = {b.question_no: b.location for b in parsed.questions}
    answers: dict[CellRef, str] = {}
    won: set[int] = set()
    for i, record in enumerate(result.submissions, 1):
        unknown = [n for n in record.question_nos if n not in location]
        if unknown:
            raise ResultsFileInvalid(f"搶答結果第 {i} 筆紀錄的題號 {unknown} 不存在於學習單中。")
        if record.outcome is SubmissionOutcome.SUCCESS:
            for n in record.question_nos:
                answers[location[n]] = record.answers[n]
                won.add(n)
    return answers, tuple(sorted(won)), tuple(n for n in sorted(location) if n not in won)
