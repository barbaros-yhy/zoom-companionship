# bot/storage.py
import sqlite3
import json
import uuid
from datetime import datetime
from pathlib import Path


class Storage:
    """Persists meeting metadata to SQLite and transcripts to local markdown files."""

    def __init__(self, db_path: str, local_dir: str):
        self.db_path = db_path
        self.local_dir = Path(local_dir)
        self.local_dir.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS meetings (
                    id TEXT PRIMARY KEY,
                    title TEXT,
                    platform TEXT,
                    meeting_url TEXT,
                    date TEXT,
                    status TEXT DEFAULT 'ongoing',
                    summary TEXT,
                    action_items TEXT DEFAULT '[]',
                    participants TEXT DEFAULT '[]'
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS segments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    meeting_id TEXT,
                    speaker TEXT,
                    text TEXT,
                    timestamp TEXT,
                    created_at TEXT
                )
            """)

    def create_meeting(self, title: str, platform: str, meeting_url: str) -> str:
        meeting_id = str(uuid.uuid4())[:8]
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO meetings (id, title, platform, meeting_url, date) VALUES (?,?,?,?,?)",
                (meeting_id, title, platform, meeting_url, datetime.utcnow().isoformat()),
            )
        return meeting_id

    def get_meeting(self, meeting_id: str) -> dict | None:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM meetings WHERE id=?", (meeting_id,)
            ).fetchone()
            return dict(row) if row else None

    def list_meetings(self) -> list[dict]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM meetings ORDER BY date DESC"
            ).fetchall()
            return [dict(r) for r in rows]

    def append_segment(self, meeting_id: str, speaker: str, text: str, timestamp: str):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO segments (meeting_id, speaker, text, timestamp, created_at) VALUES (?,?,?,?,?)",
                (meeting_id, speaker, text, timestamp, datetime.utcnow().isoformat()),
            )
        # Append to local markdown transcript file
        transcript_file = self.local_dir / f"{meeting_id}_transcript.md"
        with open(transcript_file, "a", encoding="utf-8") as f:
            f.write(f"[{timestamp}] **{speaker}:** {text}\n\n")

    def get_segments(self, meeting_id: str) -> list[dict]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM segments WHERE meeting_id=? ORDER BY id",
                (meeting_id,),
            ).fetchall()
            return [dict(r) for r in rows]

    def complete_meeting(self, meeting_id: str, summary: str, action_items: list[str]):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE meetings SET status=?, summary=?, action_items=? WHERE id=?",
                ("completed", summary, json.dumps(action_items), meeting_id),
            )
