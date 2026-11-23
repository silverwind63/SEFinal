"""由已確認學習單的解析結果產生搶答單位（research R4）。"""

from guided_buzz.domain.models import Blank, BuzzUnit, ParsedWorksheet


def _source(blanks: list[Blank]) -> str:
    label = blanks[0].source_label
    subs = "".join(b.sub_label or "" for b in blanks)
    if not label and not subs:
        return ""
    return f"（學習單第 {label or '?'} 題{subs}）"


def build_units(parsed: ParsedWorksheet) -> list[BuzzUnit]:
    """題組 → G<group_no>，其餘題目 → Q<question_no>；依最小題號排序。顯示文字不含題目敘述。"""
    by_no = {b.question_no: b for b in parsed.questions}
    units: list[BuzzUnit] = []
    for g in parsed.groups:
        blanks = [by_no[n] for n in g.question_nos]
        nos = "、".join(map(str, g.question_nos))
        units.append(BuzzUnit(f"G{g.group_no}", tuple(g.question_nos), f"題組 {g.group_no}：第 {nos} 題{_source(blanks)}"))
    for b in parsed.questions:
        if b.group_no is None:
            units.append(BuzzUnit(f"Q{b.question_no}", (b.question_no,), f"第 {b.question_no} 題{_source([b])}"))
    return sorted(units, key=lambda u: u.question_nos[0])
