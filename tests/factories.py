"""動態產生 SpreadsheetGrid 變體學習單（tasks T025），確認解析不依賴特定檔案。"""

from guided_buzz.domain.models import SheetGrid, SpreadsheetGrid

DEFAULT_ID = "TESTSHEET_abcdefghijklmnopqrstuvwxyz"


def sheet(cells: dict[str, str], merges=(), title="學習單", sheet_id=0) -> SheetGrid:
    return SheetGrid(sheet_id, title, dict(cells), tuple(merges))


def grid(*sheets: SheetGrid, spreadsheet_id=DEFAULT_ID, title="測試學習單") -> SpreadsheetGrid:
    return SpreadsheetGrid(spreadsheet_id, title, tuple(sheets))


def standard_sheet(
    count: int,
    *,
    header_row=4,
    number_col="B",
    question_cols=("C", "F"),
    answer_cols=("G", "H"),
    gap=True,
    prefilled: dict[int, str] | None = None,
    title="學習單",
    sheet_id=0,
) -> SheetGrid:
    """第 i 題（1 起算）各佔一列，作答欄位合併成一格；gap=True 時題目列之間夾空白分隔列。"""
    q1, q2 = question_cols
    a1, a2 = answer_cols
    cells = {f"{number_col}{header_row}": "題號", f"{q1}{header_row}": "題目", f"{a1}{header_row}": "作答"}
    merges = []
    if q1 != q2:
        merges.append(f"{q1}{header_row}:{q2}{header_row}")
    if a1 != a2:
        merges.append(f"{a1}{header_row}:{a2}{header_row}")
    for i in range(1, count + 1):
        row = header_row + (2 * i - 1 if gap else i)
        cells[f"{number_col}{row}"] = str(i)
        cells[f"{q1}{row}"] = f"第 {i} 題敘述"
        if q1 != q2:
            merges.append(f"{q1}{row}:{q2}{row}")
        if a1 != a2:
            merges.append(f"{a1}{row}:{a2}{row}")
        if prefilled and i in prefilled:
            cells[f"{a1}{row}"] = prefilled[i]
    return sheet(cells, merges, title, sheet_id)


def row_of(i: int, header_row=4, gap=True) -> int:
    return header_row + (2 * i - 1 if gap else i)
