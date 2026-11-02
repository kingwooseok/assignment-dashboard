"""실제 API 요청으로 저장, 필터, 날짜 계산, ICS 가져오기를 검증한다."""
from datetime import date, datetime
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from fastapi.testclient import TestClient
from icalendar import Calendar, Event

from app import create_app
from models import KST, dashboard, normalize_due


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr("app.now_kst", lambda: datetime(2026, 11, 2, 12, tzinfo=KST))
    with TestClient(create_app(tmp_path / "tasks.db")) as value:
        yield value


def task(**changes):
    return {"subject": "오픈소스SW", "title": "웹앱 보고서", "due_at": "2026-11-02", **changes}


def calendar_bytes(*events):
    calendar = Calendar()
    calendar.add("VERSION", "2.0")
    calendar.add("PRODID", "-//Assignment tests//KO")
    for values in events:
        event = Event()
        for key, value in values.items():
            event.add(key, value)
        calendar.add_component(event)
    return calendar.to_ical()


def preview(client, content, filename="tasks.ics"):
    return client.post("/api/import/preview", files={"file": (filename, content, "text/calendar")})


def selection(response, subject="테스트 과목"):
    return {"items": [{**{k: v for k, v in item.items() if k != "exists"}, "subject": item["subject"] or subject} for item in response.json()["items"]]}


def test_crud_completion_and_filter(client):
    created = client.post("/api/assignments", json=task())
    assert created.status_code == 201
    item_id = created.json()["id"]
    client.post("/api/assignments", json=task(title="자료구조 실습", subject="자료구조", due_at="2026-11-01"))
    state = client.get("/api/dashboard").json()
    assert [x["status_label"] for x in state["assignments"]] == ["기한 지남", "오늘 마감"]
    assert state["summary"] == {"today":1,"week":1,"overdue":1,"completed":0,"total":2}
    late_id = state["assignments"][0]["id"]
    assert client.patch(f"/api/assignments/{late_id}/completion", json={"completed":True}).status_code == 200
    state = client.get("/api/dashboard", params={"subject":"오픈소스SW", "q":"보고서", "status":"pending"}).json()
    assert len(state["assignments"]) == 1
    assert state["summary"]["overdue"] == 0
    assert state["summary"]["completed"] == 1
    assert client.get("/api/dashboard", params={"q":"없는 제목"}).json()["assignments"] == []
    assert client.put(f"/api/assignments/{item_id}", json=task(due_at="2026-12-31", title="수정 보고서")).status_code == 200
    state = client.get("/api/dashboard").json()
    assert state["summary"]["today"] == 0 and state["summary"]["week"] == 0
    assert state["assignments"][-1]["title"] == "수정 보고서"
    assert client.delete(f"/api/assignments/{item_id}").status_code == 200
    assert client.delete(f"/api/assignments/{item_id}").status_code == 404


@pytest.mark.parametrize("changes", [{"title":" "}, {"subject":""}, {"due_at":"2026-02-30"}, {"due_at":"2026-2-1"}, {"url":"javascript:alert(1)"}, {"url":"https://"}])
def test_invalid_input_does_not_save(client, changes):
    response = client.post("/api/assignments", json=task(**changes))
    assert response.status_code == 422
    assert isinstance(response.json()["detail"], str)
    assert client.get("/api/dashboard").json()["summary"]["total"] == 0


def test_calendar_timezone_subject_preview_and_duplicates(client):
    data = calendar_bytes(
        {"UID":"test-1", "SUMMARY":"한국어 일정", "DTSTART":datetime.fromisoformat("2026-11-02T16:00:00+00:00"), "CATEGORIES":["자료구조"], "DESCRIPTION":"첫째 줄\n둘째 줄"},
        {"UID":"test-2", "SUMMARY":"날짜만 있는 일정", "DTSTART":date(2026,11,5)},
    )
    response = preview(client, data)
    assert response.status_code == 200
    rows = response.json()["items"]
    assert rows[0]["due_at"] == "2026-11-03T01:00:00+09:00"
    assert rows[0]["subject"] == "자료구조"
    assert rows[0]["note"] == "첫째 줄\n둘째 줄"
    assert rows[1]["due_at"] == "2026-11-05"
    assert rows[1]["subject"] == ""
    assert client.get("/api/dashboard").json()["summary"]["total"] == 0
    payload = selection(response)
    assert client.post("/api/import",json=payload).json() == {"added":2,"skipped":0}
    assert client.post("/api/import",json=payload).json() == {"added":0,"skipped":2}
    assert all(item["exists"] for item in preview(client,data).json()["items"])


def test_calendar_partial_selection_and_invalid_rows(client):
    good = {"UID":"test-1","SUMMARY":"정상 일정","DTSTART":date(2026,11,5)}
    data = calendar_bytes(good, good,
        {"UID":"test-2","SUMMARY":"날짜 없는 일정"},
        {"UID":"test-3","SUMMARY":"취소된 일정","DTSTART":date(2026,11,5),"STATUS":"CANCELLED"},
        {"UID":"test-4","SUMMARY":"반복 일정","DTSTART":date(2026,11,5),"RRULE":{"FREQ":"DAILY"}},
        {"UID":"test-5","SUMMARY":"또 다른 일정","DTSTART":date(2026,11,6)})
    response = preview(client, data)
    assert len(response.json()["items"]) == 2
    assert len(response.json()["warnings"]) == 4
    payload = selection(response)
    payload["items"] = payload["items"][:1]
    assert client.post("/api/import",json=payload).json()["added"] == 1


@pytest.mark.parametrize("content,filename", [(b"broken", "broken.ics"), (b"", "empty.ics"), (b"not ics", "data.txt"), (b"x" * (2*1024*1024+1), "large.ics")])
def test_invalid_files(client,content,filename):
    assert preview(client,content,filename).status_code == 400


def test_year_month_leap_year_and_time_boundary():
    for today, due, label in [("2026-01-31","2026-02-01","D-1"),("2026-12-31","2027-01-01","D-1"),("2028-02-28","2028-03-01","D-2")]:
        reference=datetime.fromisoformat(today+"T12:00:00+09:00")
        result=dashboard([{**task(due_at=due),"id":1,"completed":False}],reference)
        assert result["assignments"][0]["status_label"] == label
    rows=[{**task(due_at="2026-11-02T10:00:00+09:00"),"id":1,"completed":False}, {**task(),"id":2,"completed":False}]
    result=dashboard(rows,datetime(2026,11,2,12,tzinfo=KST))
    assert [r["status"] for r in result["assignments"]] == ["overdue","today"]
    assert normalize_due("2026-11-02T10:00") == "2026-11-02T10:00:00+09:00"


def test_restart_restores_completion(tmp_path):
    path=tmp_path/"persistent.db"
    with TestClient(create_app(path)) as first:
        item_id=first.post("/api/assignments",json=task()).json()["id"]
        first.patch(f"/api/assignments/{item_id}/completion",json={"completed":True})
    with TestClient(create_app(path)) as second:
        item=second.get("/api/dashboard").json()["assignments"][0]
        assert item["title"] == "웹앱 보고서" and item["completed"] is True


def test_reject_foreign_origin(client):
    response=client.post("/api/assignments",json=task(),headers={"origin":"https://unrelated.example"})
    assert response.status_code == 403
