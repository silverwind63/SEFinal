import csv
import io
from uuid import uuid4

from guided_buzz.domain.models import ActivityResult, SubmissionOutcome, SubmissionRecord
from guided_buzz.export.csv_export import to_csv
from guided_buzz.worksheet.parser import parse
from tests.fakes import FakeSheetsGateway

S, N, I = SubmissionOutcome.SUCCESS, SubmissionOutcome.NOT_WON, SubmissionOutcome.INVALIDATED
PARSED_B = parse(FakeSheetsGateway().add_fixture("sample_b"), ("題號", "題目", "作答"), 500)


def result(*records):
    return ActivityResult(uuid4(), uuid4(), "teacher", True, tuple(SubmissionRecord(*r) for r in records))


def rows(text):
    return list(csv.reader(io.StringIO(text.lstrip("﻿"), newline="")))


def test_bom_crlf_header_sorting_and_group_split():
    text, count = to_csv(
        result(
            ((5,), "第三組", {5: "0"}, 2, S),
            ((5,), "第二組", {5: "1"}, 1, I),
            ((1, 2), "第一組", {1: "CPU", 2: "作業系統"}, 1, S),
            ((1, 2), "第四組", {1: "a", 2: "b"}, 2, N),
        ),
        PARSED_B,
    )
    assert text.startswith("﻿題號,組別,答案,搶答順位,結果\r\n")
    assert rows(text) == [
        ["題號", "組別", "答案", "搶答順位", "結果"],
        ["1", "第一組", "CPU", "1", "成功"],
        ["1", "第四組", "a", "2", "未搶到"],
        ["2", "第一組", "作業系統", "1", "成功"],
        ["2", "第四組", "b", "2", "未搶到"],
        ["5", "第二組", "1", "1", "無效"],
        ["5", "第三組", "0", "2", "成功"],
    ]
    assert count == 6


def test_special_characters_round_trip():
    answer = '含,逗號 與 "引號"\n還有換行'
    text, _ = to_csv(result(((6,), "第一組", {6: answer}, 1, S)), PARSED_B)
    assert rows(text)[1][2] == answer


def test_no_records_only_header():
    text, count = to_csv(result(), PARSED_B)
    assert rows(text) == [["題號", "組別", "答案", "搶答順位", "結果"]] and count == 0
