from uuid import uuid4

import pytest

from guided_buzz.domain.errors import ResultsFileInvalid
from guided_buzz.domain.models import ActivityResult, SubmissionOutcome, SubmissionRecord
from guided_buzz.results.mapping import success_answers
from guided_buzz.worksheet.parser import parse
from tests.fakes import FakeSheetsGateway

S, N, I = SubmissionOutcome.SUCCESS, SubmissionOutcome.NOT_WON, SubmissionOutcome.INVALIDATED
PARSED_B = parse(FakeSheetsGateway().add_fixture("sample_b"), ("題號", "題目", "作答"), 500)


def result(*records):
    return ActivityResult(uuid4(), uuid4(), "teacher", True, tuple(SubmissionRecord(*r) for r in records))


def test_only_success_records_and_group_maps_to_cells():
    answers, filled, unfilled = success_answers(
        result(((1, 2), "第一組", {1: "CPU", 2: "作業系統"}, 1, S), ((1, 2), "第二組", {1: "x", 2: "y"}, 2, N)), PARSED_B
    )
    assert {r.cell: t for r, t in answers.items()} == {"H5": "CPU", "H6": "作業系統"}
    assert (filled, unfilled) == ((1, 2), (3, 4, 5, 6))


def test_promoted_after_invalidation():
    answers, filled, _ = success_answers(
        result(((5,), "第二組", {5: "1"}, 1, I), ((5,), "第三組", {5: "0"}, 2, S)), PARSED_B
    )
    assert {r.cell: t for r, t in answers.items()} == {"G11": "0"} and filled == (5,)


def test_no_success_all_unfilled():
    answers, filled, unfilled = success_answers(result(((6,), "第一組", {6: "a"}, 1, N)), PARSED_B)
    assert answers == {} and filled == () and unfilled == (1, 2, 3, 4, 5, 6)


def test_unknown_question_number_rejected():
    with pytest.raises(ResultsFileInvalid) as exc:
        success_answers(result(((9,), "第一組", {9: "a"}, 1, S)), PARSED_B)
    assert "第 1 筆" in exc.value.message and "9" in exc.value.message
