import pytest

from guided_buzz.domain.errors import ImportErrorCode, ImportFailed
from guided_buzz.worksheet.parser import parse, structure_hash
from tests import factories as f
from tests.fakes import FakeSheetsGateway

LABELS = ("題號", "題目", "作答")


def run(g, limit=500):
    return parse(g, LABELS, limit)


def codes(exc):
    return [i.code for i in exc.value.issues]


def summary(parsed):
    return [(b.question_no, b.location.cell, b.source_label, b.sub_label, b.group_no) for b in parsed.questions]


def test_sample_a_matches_spec_table():
    parsed = run(FakeSheetsGateway().add_fixture("sample_a"))
    assert [b.location.cell for b in parsed.questions] == ["G5", "G7", "G9", "G11", "G13", "G15"]
    assert [b.question_no for b in parsed.questions] == [1, 2, 3, 4, 5, 6]
    assert parsed.groups == ()
    assert all(b.location.sheet_title == "學習單" for b in parsed.questions)


def test_sample_b_matches_spec_table():
    parsed = run(FakeSheetsGateway().add_fixture("sample_b"))
    assert summary(parsed) == [
        (1, "H5", "1", "（1）", 1),
        (2, "H6", "1", "（2）", 1),
        (3, "H8", "2", "（1）", 2),
        (4, "H9", "2", "（2）", 2),
        (5, "G11", "3", None, None),
        (6, "G13", "4", None, None),
    ]
    assert [(g.group_no, g.source_label, g.question_nos) for g in parsed.groups] == [(1, "1", (1, 2)), (2, "2", (3, 4))]


def test_different_layout_quickstart_v4():
    cells = {"A2": "題號", "C2": "題目", "B2": "作答", "A3": "1", "C3": "q1", "A4": "2", "C4": "q2-1", "C5": "q2-2"}
    merges = ["C2:E2", "C3:E3", "C4:E4", "C5:E5", "A4:A5"]
    parsed = run(f.grid(f.sheet(cells, merges)))
    assert [b.location.cell for b in parsed.questions] == ["B3", "B4", "B5"]
    assert [(g.group_no, g.question_nos) for g in parsed.groups] == [(1, (2, 3))]


def test_multiple_sheets_numbered_continuously_and_sheet_without_header_skipped():
    g = f.grid(
        f.sheet({"A1": "說明頁"}, title="說明", sheet_id=7),
        f.standard_sheet(2, title="第一頁", sheet_id=1),
        f.standard_sheet(3, title="第二頁", sheet_id=2, header_row=1, gap=False),
    )
    parsed = run(g)
    assert [(b.question_no, b.location.sheet_title) for b in parsed.questions] == [
        (1, "第一頁"), (2, "第一頁"), (3, "第二頁"), (4, "第二頁"), (5, "第二頁")
    ]
    assert parsed.questions[2].location.sheet_id == 2


def test_whitespace_only_answer_counts_as_blank():
    parsed = run(f.grid(f.standard_sheet(1, prefilled={1: "   "})))
    assert parsed.question_count == 1


def test_adjacent_unmerged_blanks_are_one_blank_at_leftmost():
    cells = {"B4": "題號", "C4": "題目", "G4": "作答", "B5": "1", "C5": "q"}
    parsed = run(f.grid(f.sheet(cells, ["G4:H4"])))
    assert parsed.questions[0].location.cell == "G5"


def test_header_not_found():
    with pytest.raises(ImportFailed) as exc:
        run(f.grid(f.sheet({"B4": "題號", "C4": "題目"})))
    assert codes(exc) == [ImportErrorCode.HEADER_NOT_FOUND]
    assert "題號、題目、作答" in exc.value.issues[0].message


def test_no_question_rows():
    with pytest.raises(ImportFailed) as exc:
        run(f.grid(f.standard_sheet(0)))
    assert codes(exc) == [ImportErrorCode.NO_QUESTION_ROWS]


def test_no_blank_in_row_points_to_row():
    with pytest.raises(ImportFailed) as exc:
        run(f.grid(f.standard_sheet(3, prefilled={2: "已填答案"})))
    issue = exc.value.issues[0]
    assert issue.code is ImportErrorCode.NO_BLANK_IN_ROW
    assert (issue.sheet, issue.row) == ("學習單", f.row_of(2))
    assert f"第 {f.row_of(2)} 列" in issue.message


def test_multiple_blanks_in_row():
    cells = {"B4": "題號", "C4": "題目", "G4": "作答", "B5": "1", "C5": "q", "H5": "（中間文字）"}
    with pytest.raises(ImportFailed) as exc:
        run(f.grid(f.sheet(cells, ["G4:I4"])))
    issue = exc.value.issues[0]
    assert issue.code is ImportErrorCode.MULTIPLE_BLANKS_IN_ROW and issue.row == 5
    assert "2 個空白作答區" in issue.message


def test_group_range_incomplete():
    cells = {"B4": "題號", "C4": "題目", "G4": "作答", "B5": "1", "C5": "q1"}
    with pytest.raises(ImportFailed) as exc:
        run(f.grid(f.sheet(cells, ["B5:B6", "G4:H4", "G5:H5", "G6:H6"])))
    issue = exc.value.issues[0]
    assert issue.code is ImportErrorCode.GROUP_RANGE_INCOMPLETE
    assert (issue.cell, issue.row) == ("B5", 6)


def test_too_many_questions_boundary():
    assert run(f.grid(f.standard_sheet(5)), limit=5).question_count == 5
    with pytest.raises(ImportFailed) as exc:
        run(f.grid(f.standard_sheet(6)), limit=5)
    assert codes(exc) == [ImportErrorCode.TOO_MANY_QUESTIONS]
    assert "上限 5" in exc.value.issues[0].message


def test_all_problems_reported_at_once():
    with pytest.raises(ImportFailed) as exc:
        run(f.grid(f.standard_sheet(4, prefilled={1: "x", 3: "y"})))
    assert [(i.code, i.row) for i in exc.value.issues] == [
        (ImportErrorCode.NO_BLANK_IN_ROW, f.row_of(1)),
        (ImportErrorCode.NO_BLANK_IN_ROW, f.row_of(3)),
    ]


def test_question_text_not_kept():
    fake = FakeSheetsGateway()
    grid = fake.add_fixture("sample_a")
    texts = fake.question_texts(grid.spreadsheet_id)
    assert len(texts) == 6
    assert not any(t in repr(run(grid)) for t in texts)


def test_structure_hash_changes_when_blank_moves():
    a = run(f.grid(f.standard_sheet(3)))
    b = run(f.grid(f.standard_sheet(3, gap=False)))
    assert structure_hash(a) == structure_hash(run(f.grid(f.standard_sheet(3))))
    assert structure_hash(a) != structure_hash(b)


@pytest.mark.parametrize("count", [100, 500])
def test_parse_performance(count):
    import time

    g = f.grid(f.standard_sheet(count))
    start = time.perf_counter()
    assert run(g).question_count == count
    assert time.perf_counter() - start < 10  # SC-002 中屬於本機解析的部分
