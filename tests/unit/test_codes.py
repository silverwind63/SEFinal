"""組別代碼（tasks T009）。"""

from guided_buzz.activity import codes


def test_code_charset_and_length():
    for _ in range(200):
        code = codes.new_code(set())
        assert codes.is_well_formed(code)
        assert not set(code) & set("01IO")


def test_codes_unique_within_activity():
    existing: set[str] = set()
    for _ in range(300):
        existing.add(codes.new_code(existing))
    assert len(existing) == 300


def test_normalize_strips_spaces_and_uppercases():
    assert codes.normalize(" ab c\t2 3d ") == "ABC23D"


def test_malformed_codes():
    assert not codes.is_well_formed("ABC")
    assert not codes.is_well_formed("ABCDE0")  # 0 不在字元集
    assert not codes.is_well_formed("ABCDEFG")


def test_hash_matches_only_same_code():
    assert codes.code_hash("ABC234") == codes.code_hash("ABC234")
    assert codes.code_hash("ABC234") != codes.code_hash("ABC235")
    assert "ABC234" not in codes.code_hash("ABC234")
