"""실행: python run.py. 브라우저: http://127.0.0.1:8000"""
import os
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from calendar_import import MAX_FILE_SIZE, parse_calendar
from models import AssignmentInput, CompletionInput, ImportSelection, dashboard, now_kst
from storage import Store

ROOT = Path(__file__).resolve().parent
VERSION = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
REVISION = os.environ.get("APP_REVISION", "local")


def create_app(db_path=None):
    api = FastAPI(title="과제 마감 대시보드", docs_url=None, redoc_url=None)
    store = Store(db_path or os.environ.get("ASSIGNMENT_DB", ROOT / "data" / "assignments.db"))
    api.state.store = store

    @api.middleware("http")
    async def local_requests(request: Request, call_next):
        origin = request.headers.get("origin")
        if request.method not in ("GET", "HEAD", "OPTIONS") and origin and origin != str(request.base_url).rstrip("/"):
            return JSONResponse({"detail": "앱을 실행한 주소에서 다시 시도해 주세요."}, status_code=403)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-App-Version"] = VERSION
        response.headers["X-App-Revision"] = REVISION
        return response

    @api.exception_handler(RequestValidationError)
    async def validation_error(request, error):
        labels = {"subject": "과목명", "title": "과제명", "due_at": "마감일", "note": "메모", "url": "과제 링크", "items": "가져올 일정"}
        issue = error.errors()[0]
        field = str(issue["loc"][-1])
        if issue["type"] == "value_error":
            message = issue["msg"].removeprefix("Value error, ")
        else:
            message = f"{labels.get(field, '입력값')}을 확인해 주세요. 필수 항목과 입력 길이를 확인하세요."
        return JSONResponse({"detail": message}, status_code=422)

    @api.get("/")
    def index():
        return FileResponse(ROOT / "static" / "index.html")

    @api.get("/deployment")
    def deployment_verification():
        return FileResponse(ROOT / "static" / "deployment.html")

    @api.get("/api/health")
    def health():
        # 컨테이너 교체 전에 서버와 저장소가 함께 응답하는지 확인한다.
        with store.connection() as db:
            db.execute("SELECT 1").fetchone()
        return {"status": "ok", "version": VERSION, "revision": REVISION}

    @api.get("/api/dashboard")
    def get_dashboard(q: str = "", subject: str = "", status: str = "all",
                      deadline: Literal['all', 'today', 'next3', 'overdue'] = 'all'):
        return {**dashboard(store.all(), now_kst(), q.strip(), subject, status, deadline),
                "release": {"version": VERSION, "revision": REVISION}}

    @api.post("/api/assignments", status_code=201)
    def add(item: AssignmentInput):
        return {"id": store.add(item)}

    @api.put("/api/assignments/{assignment_id}")
    def edit(assignment_id: int, item: AssignmentInput):
        if not store.update(assignment_id, item):
            raise HTTPException(404, "과제를 찾을 수 없습니다. 목록을 새로고침해 주세요.")
        return {"ok": True}

    @api.patch("/api/assignments/{assignment_id}/completion")
    def complete(assignment_id: int, item: CompletionInput):
        if not store.complete(assignment_id, item.completed):
            raise HTTPException(404, "과제를 찾을 수 없습니다.")
        return {"ok": True}

    @api.delete("/api/assignments/{assignment_id}")
    def delete(assignment_id: int):
        if not store.delete(assignment_id):
            raise HTTPException(404, "과제를 찾을 수 없습니다.")
        return {"ok": True}

    @api.post("/api/import/preview")
    async def preview(file: UploadFile):
        if not (file.filename or "").lower().endswith(".ics"):
            raise HTTPException(400, ".ics 확장자의 캘린더 파일을 선택해 주세요.")
        try:
            content = await file.read(MAX_FILE_SIZE + 1)
            keys = {row["source_key"] for row in store.all() if row["source_key"]}
            return parse_calendar(content, keys)
        except ValueError as error:
            raise HTTPException(400, str(error)) from error
        finally:
            await file.close()

    @api.post("/api/import")
    def import_selected(selection: ImportSelection):
        return store.import_items(selection.items)

    @api.get("/sample_assignments.ics")
    def sample():
        return FileResponse(ROOT / "sample_assignments.ics", media_type="text/calendar", filename="sample_assignments.ics")

    api.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")
    return api


app = create_app()
