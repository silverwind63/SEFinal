"""FakeSheetsGateway：以記憶體中的試算表取代 Google 服務，測試不連網。"""

import json
from dataclasses import replace
from pathlib import Path

from guided_buzz.domain.models import CellRef, SpreadsheetGrid
from guided_buzz.sheets.google_gateway import grid_from_response

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "sheets"


class FakeSheetsGateway:
    account_email = "teacher@example.com"

    def __init__(self):
        self.sheets: dict[str, SpreadsheetGrid] = {}
        self.fetch_errors: dict[str, Exception] = {}
        self.write_errors: dict[str, Exception] = {}
        self.writes: list[tuple[str, dict[CellRef, str]]] = []

    def add(self, grid: SpreadsheetGrid) -> SpreadsheetGrid:
        self.sheets[grid.spreadsheet_id] = grid
        return grid

    def add_fixture(self, name: str) -> SpreadsheetGrid:
        return self.add(grid_from_response(json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))))

    def set_cell(self, spreadsheet_id: str, sheet_title: str, cell: str, text: str | None) -> None:
        grid = self.sheets[spreadsheet_id]
        sheets = []
        for sheet in grid.sheets:
            if sheet.title == sheet_title:
                values = dict(sheet.values)
                if text is None:
                    values.pop(cell, None)
                else:
                    values[cell] = text
                sheet = replace(sheet, values=values)
            sheets.append(sheet)
        self.sheets[spreadsheet_id] = replace(grid, sheets=tuple(sheets))

    def fetch_grid(self, spreadsheet_id: str) -> SpreadsheetGrid:
        if spreadsheet_id in self.fetch_errors:
            raise self.fetch_errors[spreadsheet_id]
        if spreadsheet_id not in self.sheets:
            from guided_buzz.domain.errors import SheetNotFound

            raise SheetNotFound()
        return self.sheets[spreadsheet_id]

    def write_cells(self, spreadsheet_id: str, values: dict[CellRef, str]) -> None:
        if spreadsheet_id in self.write_errors:
            raise self.write_errors[spreadsheet_id]
        self.writes.append((spreadsheet_id, dict(values)))
        for ref, text in values.items():
            self.set_cell(spreadsheet_id, ref.sheet_title, ref.cell, text)
