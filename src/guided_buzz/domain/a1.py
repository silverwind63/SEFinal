"""A1 表示法與（列, 欄）索引之間的轉換。列、欄皆從 1 開始。"""

import re

_A1 = re.compile(r"^([A-Z]{1,3})([1-9][0-9]*)$")


def col_letters(col: int) -> str:
    letters = ""
    while col:
        col, rem = divmod(col - 1, 26)
        letters = chr(65 + rem) + letters
    return letters


def to_a1(row: int, col: int) -> str:
    return f"{col_letters(col)}{row}"


def parse_a1(cell: str) -> tuple[int, int]:
    match = _A1.match(cell)
    if not match:
        raise ValueError(f"不是合法的儲存格位置：{cell}")
    col = 0
    for ch in match.group(1):
        col = col * 26 + ord(ch) - 64
    return int(match.group(2)), col


def parse_range(rng: str) -> tuple[int, int, int, int]:
    """'G5:H6' → (起列, 起欄, 迄列, 迄欄)。"""
    start, end = rng.split(":")
    r1, c1 = parse_a1(start)
    r2, c2 = parse_a1(end)
    return r1, c1, r2, c2
