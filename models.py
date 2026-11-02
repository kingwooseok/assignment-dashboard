"""입력값 검증과 한국 시간 기준 마감 계산."""
import re
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator

KST = ZoneInfo("Asia/Seoul")


def now_kst():
    return datetime.now(KST)


def normalize_due(value):
    """날짜만 입력했다면 날짜로, 시각이 있으면 한국 시간으로 저장한다."""
    value = value.strip()
    try:
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            return date.fromisoformat(value).isoformat()
        if not re.match(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}", value):
            raise ValueError
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed.replace(tzinfo=parsed.tzinfo or KST).astimezone(KST).isoformat(timespec="seconds")
    except (ValueError, OverflowError):
        raise ValueError("마감일을 올바른 날짜와 시각으로 입력해 주세요.") from None


class AssignmentInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    subject: str = Field(min_length=1, max_length=80)
    title: str = Field(min_length=1, max_length=160)
    due_at: str = Field(max_length=40)
    note: str = Field(default="", max_length=2000)
    url: str = Field(default="", max_length=2000)

    @field_validator("due_at")
    @classmethod
    def check_due(cls, value):
        return normalize_due(value)

    @field_validator("url")
    @classmethod
    def check_url(cls, value):
        if value:
            try:
                parsed = urlsplit(value)
                if parsed.scheme not in ("http", "https") or not parsed.hostname or any(c.isspace() for c in value):
                    raise ValueError
            except ValueError:
                raise ValueError("과제 링크는 http:// 또는 https://로 시작하는 주소를 입력해 주세요.") from None
        return value


class ImportedAssignment(AssignmentInput):
    source_key: str = Field(pattern=r"^ics:[0-9a-f]{64}$")


class ImportSelection(BaseModel):
    items: list[ImportedAssignment] = Field(min_length=1, max_length=500)


class CompletionInput(BaseModel):
    completed: bool


def due_details(item, reference):
    due = item["due_at"]
    has_time = "T" in due
    instant = datetime.fromisoformat(due) if has_time else datetime.combine(date.fromisoformat(due), time.max, KST)
    day = instant.astimezone(KST).date()
    days = (day - reference.date()).days
    overdue = instant < reference
    if item["completed"]:
        status, label = "completed", "완료"
    elif overdue:
        status, label = "overdue", "기한 지남"
    elif days == 0:
        status, label = "today", "오늘 마감"
    else:
        status, label = "upcoming", f"D-{days}"
    return {"status": status, "status_label": label, "days_left": days,
            "due_date": day.isoformat(), "due_time": instant.strftime("%H:%M") if has_time else None,
            "sort_key": instant.isoformat()}


def dashboard(assignments, reference, query="", subject="", status="all"):
    """집계는 전체 목록을 기준으로 하고 검색·필터는 목록에 적용한다."""
    reference = reference.astimezone(KST)
    rows = [{**item, **due_details(item, reference)} for item in assignments]
    today = reference.date()
    week_end = today + timedelta(days=6 - today.weekday())
    pending = [row for row in rows if not row["completed"]]
    summary = {
        "today": sum(row["due_date"] == today.isoformat() for row in pending),
        "week": sum(today.isoformat() <= row["due_date"] <= week_end.isoformat() for row in pending),
        "overdue": sum(row["status"] == "overdue" for row in pending),
        "completed": sum(row["completed"] for row in rows),
        "total": len(rows),
    }
    subjects = sorted({row["subject"] for row in rows})
    future = sorted((row for row in pending if row["status"] != "overdue"), key=lambda row: row["sort_key"])
    if query:
        rows = [row for row in rows if query.casefold() in row["title"].casefold()]
    if subject:
        rows = [row for row in rows if row["subject"] == subject]
    if status == "pending":
        rows = [row for row in rows if not row["completed"]]
    elif status == "completed":
        rows = [row for row in rows if row["completed"]]
    rows.sort(key=lambda row: (row["sort_key"], row["id"]))
    return {"assignments": rows, "summary": summary, "subjects": subjects,
            "today": today.isoformat(), "week_end": week_end.isoformat(), "next": future[0] if future else None}
