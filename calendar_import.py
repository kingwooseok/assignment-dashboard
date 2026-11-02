"""ICS 파일을 과제 후보로 변환한다. 저장은 사용자가 선택한 뒤 진행한다."""
from datetime import date, datetime
from hashlib import sha256

from icalendar import Calendar
from models import AssignmentInput, KST

MAX_FILE_SIZE = 2 * 1024 * 1024


def parse_calendar(content, existing_keys):
    if not content or len(content) > MAX_FILE_SIZE:
        raise ValueError("빈 파일은 가져올 수 없습니다. 파일은 2MB 이하로 선택해 주세요.")
    try:
        calendar = Calendar.from_ical(content)
        if calendar.name != "VCALENDAR":
            raise ValueError
    except Exception:
        raise ValueError("캘린더 파일을 읽을 수 없습니다. 올바른 .ics 파일을 선택해 주세요.") from None
    items, warnings, seen = [], [], set()
    events = calendar.walk("VEVENT")
    if len(events) > 500:
        raise ValueError("한 번에 최대 500개의 일정을 가져올 수 있습니다.")
    for number, event in enumerate(events, 1):
        title = str(event.get("SUMMARY", "")).strip()
        try:
            if event.get("STATUS") == "CANCELLED":
                warnings.append(f"{number}번 일정: 취소된 일정은 건너뛰었습니다.")
                continue
            if event.get("RRULE") or event.get("RDATE"):
                warnings.append(f"{number}번 일정: 반복 일정은 개별 일정으로 내보낸 후 가져와 주세요.")
                continue
            # 학교 캘린더의 과제 일정은 DTSTART를 마감으로 사용한다.
            start = event.decoded("DTSTART")
            if isinstance(start, datetime):
                tzid = str(event["DTSTART"].params.get("TZID", ""))
                if tzid and start.tzinfo is None:
                    raise ValueError("시간대 정보를 읽을 수 없습니다.")
                due = start.replace(tzinfo=start.tzinfo or KST).astimezone(KST).isoformat(timespec="seconds")
            elif isinstance(start, date):
                due = start.isoformat()
            else:
                raise ValueError("날짜를 읽을 수 없습니다.")
            categories = event.get("CATEGORIES")
            if isinstance(categories, list):
                categories = categories[0] if categories else None
            course = str(categories.cats[0]).strip() if categories and categories.cats else ""
            note = str(event.get("DESCRIPTION", "")).strip()
            url = str(event.get("URL", "")).strip()
            if url and not url.lower().startswith(("https://", "http://")):
                warnings.append(f"{number}번 일정: 웹 주소가 아닌 링크를 제외했습니다.")
                url = ""
            parsed = AssignmentInput(subject=course or "미지정", title=title, due_at=due, note=note, url=url)
            uid = str(event.get("UID", "")).strip()
            recurrence = str(event.get("RECURRENCE-ID", ""))
            identity = f"uid:{uid}|{recurrence}" if uid else f"event:{title}|{due}|{note}|{url}"
            key = "ics:" + sha256(identity.encode("utf-8")).hexdigest()
            if key in seen:
                warnings.append(f"{number}번 일정: 파일 안의 중복 일정을 제외했습니다.")
                continue
            seen.add(key)
            items.append({**parsed.model_dump(), "subject": course, "source_key": key, "exists": key in existing_keys})
        except (ValueError, KeyError, TypeError, AttributeError):
            warnings.append(f"{number}번 일정: 제목·날짜·내용을 읽을 수 없어 건너뛰었습니다.")
    if not events:
        raise ValueError("파일에 가져올 일정(VEVENT)이 없습니다.")
    return {"items": items, "warnings": warnings}
