"""SQLite 連線與資料表（data-model.md「SQLite 資料表」）。"""

import sqlite3
from contextlib import contextmanager
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS worksheets (
    id TEXT PRIMARY KEY,
    owner TEXT NOT NULL,
    spreadsheet_id TEXT NOT NULL,
    spreadsheet_title TEXT NOT NULL,
    structure_hash TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    confirmed_at TEXT
);
CREATE TABLE IF NOT EXISTS questions (
    worksheet_id TEXT NOT NULL REFERENCES worksheets(id),
    question_no INTEGER NOT NULL,
    sheet_id INTEGER NOT NULL,
    sheet_title TEXT NOT NULL,
    cell TEXT NOT NULL,
    source_label TEXT,
    sub_label TEXT,
    group_no INTEGER,
    PRIMARY KEY (worksheet_id, question_no)
);
CREATE TABLE IF NOT EXISTS question_groups (
    worksheet_id TEXT NOT NULL REFERENCES worksheets(id),
    group_no INTEGER NOT NULL,
    source_label TEXT,
    PRIMARY KEY (worksheet_id, group_no)
);
CREATE TABLE IF NOT EXISTS writebacks (
    id TEXT PRIMARY KEY,
    worksheet_id TEXT NOT NULL REFERENCES worksheets(id),
    activity_id TEXT NOT NULL,
    filled TEXT NOT NULL,
    unfilled TEXT NOT NULL,
    skipped_non_empty TEXT NOT NULL,
    created_at TEXT NOT NULL
);
-- 002 搶答活動（specs/002-online-buzz-activity/data-model.md）
CREATE TABLE IF NOT EXISTS activities (
    id TEXT PRIMARY KEY,
    worksheet_id TEXT NOT NULL REFERENCES worksheets(id),
    owner TEXT NOT NULL,
    phase TEXT NOT NULL,
    fairness_enabled INTEGER NOT NULL,
    cooldown_seconds INTEGER NOT NULL,
    cooldown_lead INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    started_at TEXT,
    ended_at TEXT
);
CREATE TABLE IF NOT EXISTS teams (
    activity_id TEXT NOT NULL REFERENCES activities(id),
    team_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    code_hash TEXT NOT NULL,
    code_version INTEGER NOT NULL,
    PRIMARY KEY (activity_id, team_id),
    UNIQUE (activity_id, name)
);
CREATE TABLE IF NOT EXISTS submissions (
    activity_id TEXT NOT NULL REFERENCES activities(id),
    id INTEGER NOT NULL,
    unit_key TEXT NOT NULL,
    team_id INTEGER NOT NULL,
    rank INTEGER NOT NULL,
    outcome TEXT NOT NULL,
    received_at TEXT NOT NULL,
    invalidated_at TEXT,
    PRIMARY KEY (activity_id, id),
    UNIQUE (activity_id, unit_key, team_id),
    UNIQUE (activity_id, unit_key, rank),
    FOREIGN KEY (activity_id, team_id) REFERENCES teams(activity_id, team_id)
);
CREATE TABLE IF NOT EXISTS submission_answers (
    activity_id TEXT NOT NULL,
    submission_id INTEGER NOT NULL,
    question_no INTEGER NOT NULL,
    answer TEXT NOT NULL,
    PRIMARY KEY (activity_id, submission_id, question_no),
    FOREIGN KEY (activity_id, submission_id) REFERENCES submissions(activity_id, id)
);
"""


class Database:
    def __init__(self, data_dir: Path):
        data_dir.mkdir(parents=True, exist_ok=True)
        self.path = data_dir / "guided_buzz.db"
        with self.transaction() as conn:
            conn.executescript(SCHEMA)

    @contextmanager
    def transaction(self):
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            with conn:
                yield conn
        finally:
            conn.close()
