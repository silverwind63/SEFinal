import json
from uuid import UUID

import pytest

from guided_buzz.domain.errors import NotFound, ResultsFileInvalid
from guided_buzz.domain.models import SubmissionOutcome
from guided_buzz.results.json_provider import JsonFileResultsProvider

ACTIVITY = "11111111-1111-1111-1111-111111111111"
WORKSHEET = "22222222-2222-2222-2222-222222222222"


def write(tmp_path, submissions, owner="teacher", name=ACTIVITY):
    data = {"activity_id": ACTIVITY, "worksheet_id": WORKSHEET, "owner": owner, "ended": True, "submissions": submissions}
    (tmp_path / f"{name}.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return JsonFileResultsProvider(tmp_path)


EXAMPLE = [
    {"question_nos": [1, 2], "team_name": "第一組", "answers": {"1": "CPU", "2": "作業系統"}, "rank": 1, "outcome": "success"},
    {"question_nos": [5], "team_name": "第二組", "answers": {"5": "0"}, "rank": 1, "outcome": "invalidated"},
    {"question_nos": [5], "team_name": "第三組", "answers": {"5": "0"}, "rank": 2, "outcome": "success"},
]


def test_loads_contract_example(tmp_path):
    result = write(tmp_path, EXAMPLE).get_result(UUID(ACTIVITY), "teacher")
    assert result.worksheet_id == UUID(WORKSHEET) and result.ended
    assert result.submissions[0].answers == {1: "CPU", 2: "作業系統"}
    assert result.submissions[1].outcome is SubmissionOutcome.INVALIDATED


@pytest.mark.parametrize("activity_id", ["../etc/passwd", "not-a-uuid", "../" + ACTIVITY])
def test_rejects_non_uuid(tmp_path, activity_id):
    with pytest.raises(NotFound):
        write(tmp_path, EXAMPLE).get_result(activity_id, "teacher")


def test_missing_file(tmp_path):
    with pytest.raises(NotFound):
        JsonFileResultsProvider(tmp_path).get_result(UUID(ACTIVITY), "teacher")


def test_requester_mismatch(tmp_path):
    with pytest.raises(NotFound):
        write(tmp_path, EXAMPLE, owner="someone-else").get_result(UUID(ACTIVITY), "teacher")


def test_two_successes_rejected(tmp_path):
    bad = EXAMPLE + [{"question_nos": [1, 2], "team_name": "第四組", "answers": {"1": "a", "2": "b"}, "rank": 2, "outcome": "success"}]
    with pytest.raises(ResultsFileInvalid):
        write(tmp_path, bad).get_result(UUID(ACTIVITY), "teacher")


def test_answer_keys_mismatch_names_record(tmp_path):
    bad = [{"question_nos": [1, 2], "team_name": "第一組", "answers": {"1": "a"}, "rank": 1, "outcome": "success"}]
    with pytest.raises(ResultsFileInvalid) as exc:
        write(tmp_path, bad).get_result(UUID(ACTIVITY), "teacher")
    assert "第 1 筆" in exc.value.message
