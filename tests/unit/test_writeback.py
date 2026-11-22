from dataclasses import replace

import pytest

from guided_buzz.domain.errors import StructureChanged
from guided_buzz.domain.models import CellRef
from guided_buzz.worksheet.parser import parse
from guided_buzz.worksheet.writeback import plan, verify_unchanged
from tests import factories as f
from tests.fakes import FakeSheetsGateway

LABELS = ("題號", "題目", "作答")


def ref(cell, title="學習單"):
    return CellRef(0, title, cell)


def sample_b():
    fake = FakeSheetsGateway()
    grid = fake.add_fixture("sample_b")
    return fake, grid, parse(grid, LABELS, 500)


def test_plan_writes_only_blank_cells():
    fake, grid, _ = sample_b()
    fake.set_cell(grid.spreadsheet_id, "學習單", "H6", "老師的筆記")
    fake.set_cell(grid.spreadsheet_id, "學習單", "G11", "   ")
    to_write, skipped = plan({ref("H5"): "CPU", ref("H6"): "作業系統", ref("G11"): "0"}, fake.sheets[grid.spreadsheet_id])
    assert to_write == {ref("H5"): "CPU", ref("G11"): "0"}
    assert skipped == {ref("H6")}


@pytest.mark.parametrize("answer", ["第一行\n第二行", '<&>"', "=1+1", "答案😀", "長" * 1000])
def test_answers_kept_verbatim(answer):
    _, grid, _ = sample_b()
    to_write, _ = plan({ref("H5"): answer}, grid)
    assert to_write[ref("H5")] == answer


def test_verify_accepts_unchanged_and_filled_blanks():
    fake, grid, parsed = sample_b()
    verify_unchanged(parsed, grid, LABELS, 500)
    fake.set_cell(grid.spreadsheet_id, "學習單", "H5", "老師已填")
    verify_unchanged(parsed, fake.sheets[grid.spreadsheet_id], LABELS, 500)


def test_verify_detects_moved_blanks():
    parsed = parse(f.grid(f.standard_sheet(3)), LABELS, 500)
    with pytest.raises(StructureChanged) as exc:
        verify_unchanged(parsed, f.grid(f.standard_sheet(3, gap=False)), LABELS, 500)
    assert "第 2 題" in exc.value.message


def test_verify_detects_question_count_change():
    parsed = parse(f.grid(f.standard_sheet(3)), LABELS, 500)
    with pytest.raises(StructureChanged) as exc:
        verify_unchanged(parsed, f.grid(f.standard_sheet(4)), LABELS, 500)
    assert "題數" in exc.value.message


def test_verify_detects_broken_sheet():
    parsed = parse(f.grid(f.standard_sheet(2)), LABELS, 500)
    broken = f.grid(f.sheet({"A1": "沒有表頭了"}))
    with pytest.raises(StructureChanged):
        verify_unchanged(parsed, broken, LABELS, 500)
