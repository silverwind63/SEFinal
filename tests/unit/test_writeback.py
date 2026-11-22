from dataclasses import replace

import pytest

from guided_buzz.domain.errors import StructureChanged
from guided_buzz.domain.models import CellRef
from guided_buzz.worksheet.parser import parse
from guided_buzz.worksheet.writeback import plan, verify_unchanged
from tests import factories as f
from tests.fakes import FakeSheetsGateway

LABELS = ("題號", "題目", "作答")


SAMPLE_B_SHEET_ID = FakeSheetsGateway().add_fixture("sample_b").sheets[0].sheet_id


def ref(cell, title="學習單"):
    return CellRef(SAMPLE_B_SHEET_ID, title, cell)


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
    with pytest.raises(StructureChanged) as exc:
        verify_unchanged(parsed, broken, LABELS, 500)
    assert "插入或刪除" in exc.value.message and "找不到表頭列" in exc.value.message


def test_inserted_row_message_names_likely_cause():
    """人工驗證 V5-6：插入一列後，已寫回的答案移到別列，重新解析會說「第 N 列沒有填空格」；訊息要先講結構改變的可能原因。"""
    fake, grid, parsed = sample_b()
    fake.set_cell(grid.spreadsheet_id, "學習單", "G11", "0")  # 模擬已寫回的答案
    moved = f.grid(f.standard_sheet(4, prefilled={3: "0"}), spreadsheet_id=grid.spreadsheet_id)
    with pytest.raises(StructureChanged) as exc:
        verify_unchanged(parsed, moved, LABELS, 500)
    message = exc.value.message
    assert message.startswith("學習單的結構和匯入時不同（例如插入或刪除了列）")
    assert message.endswith("請重新匯入學習單後再寫回。")
