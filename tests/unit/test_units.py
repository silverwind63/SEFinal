"""搶答單位的產生（tasks T008）。"""

import pytest

from guided_buzz.activity.units import build_units
from guided_buzz.domain.models import BuzzUnit
from guided_buzz.worksheet.parser import parse
from tests import factories as f
from tests.fakes import FakeSheetsGateway

LABELS = ("題號", "題目", "作答")


def units_of(grid):
    return build_units(parse(grid, LABELS, 500))


def test_sample_b_gives_two_groups_and_two_singles():
    fake = FakeSheetsGateway()
    units = units_of(fake.add_fixture("sample_b"))
    assert [(u.key, u.question_nos) for u in units] == [("G1", (1, 2)), ("G2", (3, 4)), ("Q5", (5,)), ("Q6", (6,))]
    assert units[0].display.startswith("題組 1：第 1、2 題")
    assert "（1）（2）" in units[0].display


def test_sample_a_gives_six_singles():
    units = units_of(FakeSheetsGateway().add_fixture("sample_a"))
    assert [u.key for u in units] == ["Q1", "Q2", "Q3", "Q4", "Q5", "Q6"]


def test_group_in_the_middle_is_sorted_by_first_question():
    cells = {"A2": "題號", "B2": "題目", "C2": "作答", "A3": "1", "B3": "q1", "A4": "2", "B4": "q2a", "B5": "q2b", "A6": "3", "B6": "q3"}
    units = units_of(f.grid(f.sheet(cells, ["A4:A5"])))
    assert [(u.key, u.question_nos) for u in units] == [("Q1", (1,)), ("G1", (2, 3)), ("Q4", (4,))]


def test_display_does_not_contain_question_text():
    fake = FakeSheetsGateway()
    grid = fake.add_fixture("sample_b")
    texts = fake.question_texts(grid.spreadsheet_id)
    for unit in units_of(grid):
        assert not any(t in unit.display for t in texts)


@pytest.mark.parametrize("key,nos", [("X1", (1,)), ("Q2", (3,)), ("G1", (1,)), ("Q1", ()), ("G1", (2, 1))])
def test_invalid_buzz_unit_rejected(key, nos):
    with pytest.raises(ValueError):
        BuzzUnit(key, nos, "x")
