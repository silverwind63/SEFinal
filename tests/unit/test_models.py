from datetime import datetime, timezone
from uuid import uuid4

import pytest

from guided_buzz.domain.models import (
    ActivityResult,
    Blank,
    CellRef,
    ParsedWorksheet,
    QuestionGroup,
    SubmissionOutcome,
    SubmissionRecord,
    Worksheet,
    WorksheetStatus,
)


def ref(cell="G5"):
    return CellRef(sheet_id=0, sheet_title="學習單", cell=cell)


def parsed():
    blanks = (Blank(1, ref("H5"), "1", "（1）", 1), Blank(2, ref("H6"), "1", "（2）", 1), Blank(3, ref("G8"), "2", None, None))
    return ParsedWorksheet(questions=blanks, groups=(QuestionGroup(1, "1", (1, 2)),))


def record(nos=(1,), answers=None, rank=1, outcome=SubmissionOutcome.SUCCESS):
    return SubmissionRecord(nos, "第一組", answers if answers is not None else {n: "x" for n in nos}, rank, outcome)


def test_valid_models():
    p = parsed()
    assert p.question_count == 3 and p.group_count == 1
    ws = Worksheet(uuid4(), "teacher", "1PXXwWiBKJNpPkLRoJLMzZWsAh4Jzn2bThHTeRAiq3Hg", "範例", "h", WorksheetStatus.PENDING, p, datetime.now(timezone.utc))
    assert ws.status is WorksheetStatus.PENDING
    ActivityResult(uuid4(), ws.id, "teacher", True, (record((1, 2)), record((3,), rank=1)))


@pytest.mark.parametrize("cell", ["g5", "G0", "5G", "ABCD1", ""])
def test_bad_cell_ref(cell):
    with pytest.raises(ValueError):
        ref(cell)


@pytest.mark.parametrize("sid", ["short", "has space in the id 123456", "x" * 101])
def test_bad_spreadsheet_id(sid):
    with pytest.raises(ValueError):
        Worksheet(uuid4(), "teacher", sid, "t", "h", WorksheetStatus.PENDING, parsed(), datetime.now(timezone.utc))


@pytest.mark.parametrize("nos", [(1,), (1, 3), (2, 1)])
def test_group_needs_two_consecutive(nos):
    with pytest.raises(ValueError):
        QuestionGroup(1, "1", nos)


def test_question_numbers_must_be_consecutive():
    with pytest.raises(ValueError):
        ParsedWorksheet(questions=(Blank(1, ref("G5"), None, None, None), Blank(3, ref("G7"), None, None, None)), groups=())


def test_answers_keys_must_match():
    with pytest.raises(ValueError):
        record((1, 2), answers={1: "a"})


def test_rank_at_least_one():
    with pytest.raises(ValueError):
        record(rank=0)


def test_two_successes_for_same_unit_rejected():
    with pytest.raises(ValueError):
        ActivityResult(uuid4(), uuid4(), "teacher", True, (record((1,)), record((1,), rank=2)))
