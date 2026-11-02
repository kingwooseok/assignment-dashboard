"""SQLite 저장소. 앱 재실행 후에도 과제와 완료 상태를 유지한다."""
from contextlib import contextmanager
from pathlib import Path
import sqlite3

from models import now_kst


class Store:
    def __init__(self, path):
        self.path = Path(path)

    @contextmanager
    def connection(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        try:
            with db:
                db.execute("""CREATE TABLE IF NOT EXISTS assignments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, subject TEXT NOT NULL,
                    title TEXT NOT NULL, due_at TEXT NOT NULL, note TEXT NOT NULL DEFAULT '',
                    url TEXT NOT NULL DEFAULT '', completed INTEGER NOT NULL DEFAULT 0,
                    source_key TEXT UNIQUE, created_at TEXT NOT NULL
                )""")
                yield db
        finally:
            db.close()

    def all(self):
        with self.connection() as db:
            rows = [dict(row) for row in db.execute("SELECT * FROM assignments")]
        for row in rows:
            row["completed"] = bool(row["completed"])
        return rows

    def add(self, item):
        with self.connection() as db:
            cursor = db.execute("INSERT INTO assignments(subject,title,due_at,note,url,created_at) VALUES(?,?,?,?,?,?)",
                                (item.subject, item.title, item.due_at, item.note, item.url, now_kst().isoformat()))
            return cursor.lastrowid

    def update(self, assignment_id, item):
        with self.connection() as db:
            return db.execute("UPDATE assignments SET subject=?,title=?,due_at=?,note=?,url=? WHERE id=?",
                              (item.subject, item.title, item.due_at, item.note, item.url, assignment_id)).rowcount

    def complete(self, assignment_id, completed):
        with self.connection() as db:
            return db.execute("UPDATE assignments SET completed=? WHERE id=?", (int(completed), assignment_id)).rowcount

    def delete(self, assignment_id):
        with self.connection() as db:
            return db.execute("DELETE FROM assignments WHERE id=?", (assignment_id,)).rowcount

    def import_items(self, items):
        """UID 기반 고유 키와 DB 제약으로 중복을 방지한다."""
        added = 0
        with self.connection() as db:
            for item in items:
                result = db.execute("""INSERT INTO assignments(subject,title,due_at,note,url,source_key,created_at)
                    VALUES(?,?,?,?,?,?,?) ON CONFLICT(source_key) DO NOTHING""",
                    (item.subject, item.title, item.due_at, item.note, item.url, item.source_key, now_kst().isoformat()))
                added += result.rowcount
        return {"added": added, "skipped": len(items) - added}
