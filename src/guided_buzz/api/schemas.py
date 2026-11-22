"""API 請求與回應 schema（contracts/http-api.md），由 domain 模型轉換而來。"""

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    password: str = Field(min_length=1, max_length=128)


class TokenOut(BaseModel):
    token: str
    expires_in: int


class SessionOut(BaseModel):
    owner: str


class ImportRequest(BaseModel):
    spreadsheet_url: str = Field(min_length=1, max_length=2048)


class QuestionOut(BaseModel):
    question_no: int
    sheet: str
    cell: str
    source_label: str | None
    sub_label: str | None
    group_no: int | None


class GroupOut(BaseModel):
    group_no: int
    source_label: str | None
    question_nos: list[int]


class WorksheetPreview(BaseModel):
    id: str
    status: str
    spreadsheet_id: str
    spreadsheet_title: str
    question_count: int
    group_count: int
    questions: list[QuestionOut]
    groups: list[GroupOut]

    @classmethod
    def of(cls, ws) -> "WorksheetPreview":
        p = ws.parsed
        return cls(
            id=str(ws.id),
            status=ws.status.value,
            spreadsheet_id=ws.spreadsheet_id,
            spreadsheet_title=ws.spreadsheet_title,
            question_count=p.question_count,
            group_count=p.group_count,
            questions=[
                QuestionOut(question_no=b.question_no, sheet=b.location.sheet_title, cell=b.location.cell, source_label=b.source_label, sub_label=b.sub_label, group_no=b.group_no)
                for b in p.questions
            ],
            groups=[GroupOut(group_no=g.group_no, source_label=g.source_label, question_nos=list(g.question_nos)) for g in p.groups],
        )


class WorksheetSummary(BaseModel):
    id: str
    spreadsheet_title: str
    status: str
    question_count: int
    group_count: int
    created_at: str


class StatusOut(BaseModel):
    id: str
    status: str


class WritebackRequest(BaseModel):
    activity_id: str = Field(min_length=1, max_length=64)


class WritebackOut(BaseModel):
    filled: list[int]
    unfilled: list[int]
    skipped_non_empty: list[int]
