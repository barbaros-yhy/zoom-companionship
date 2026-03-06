# bot/tests/test_storage.py
import pytest
import json
from pathlib import Path
from bot.storage import Storage


@pytest.fixture
def storage(tmp_path):
    db_path = str(tmp_path / "test.db")
    return Storage(db_path=db_path, local_dir=str(tmp_path))


def test_create_meeting(storage):
    meeting_id = storage.create_meeting(
        title="Weekly Sync",
        platform="zoom",
        meeting_url="https://zoom.us/j/123",
    )
    assert meeting_id is not None
    assert len(meeting_id) == 8
    meeting = storage.get_meeting(meeting_id)
    assert meeting["title"] == "Weekly Sync"
    assert meeting["platform"] == "zoom"
    assert meeting["status"] == "ongoing"


def test_get_meeting_not_found(storage):
    assert storage.get_meeting("nonexistent") is None


def test_append_segment_creates_db_record(storage):
    meeting_id = storage.create_meeting("Test", "zoom", "https://zoom.us/j/1")
    storage.append_segment(meeting_id, speaker="Barbaros", text="Merhaba", timestamp="00:00:05")
    segments = storage.get_segments(meeting_id)
    assert len(segments) == 1
    assert segments[0]["speaker"] == "Barbaros"
    assert segments[0]["text"] == "Merhaba"
    assert segments[0]["timestamp"] == "00:00:05"


def test_append_segment_writes_markdown_file(storage, tmp_path):
    meeting_id = storage.create_meeting("Test", "zoom", "https://zoom.us/j/1")
    storage.append_segment(meeting_id, speaker="Barbaros", text="Merhaba", timestamp="00:00:05")
    transcript_file = tmp_path / f"{meeting_id}_transcript.md"
    assert transcript_file.exists()
    content = transcript_file.read_text()
    assert "[00:00:05]" in content
    assert "**Barbaros:**" in content
    assert "Merhaba" in content


def test_complete_meeting(storage):
    meeting_id = storage.create_meeting("Test", "zoom", "https://zoom.us/j/1")
    storage.complete_meeting(
        meeting_id,
        summary="Toplanti ozeti",
        action_items=["Barbaros: rapor yaz", "Ahmet: sunum hazirla"],
    )
    meeting = storage.get_meeting(meeting_id)
    assert meeting["status"] == "completed"
    assert meeting["summary"] == "Toplanti ozeti"
    items = json.loads(meeting["action_items"])
    assert "Barbaros: rapor yaz" in items


def test_list_meetings(storage):
    storage.create_meeting("Meeting A", "zoom", "https://zoom.us/j/1")
    storage.create_meeting("Meeting B", "zoom", "https://zoom.us/j/2")
    meetings = storage.list_meetings()
    assert len(meetings) == 2
