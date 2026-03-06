# Zoom Companion Bot — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a self-hosted meeting bot that joins Zoom, transcribes in real-time with speaker identification (TR+EN), and generates post-meeting summaries.

**Architecture:** Playwright headless Chromium joins Zoom web client; PulseAudio captures meeting audio; Speaches (faster-whisper large-v3-turbo) transcribes in real-time; caption scraping maps speaker names; Next.js dashboard shows live transcript; Claude Haiku generates post-meeting summaries.

**Tech Stack:** Python 3.11, Playwright, PulseAudio, Speaches (Docker), Node.js 20, AWS Lambda, Next.js 14, AWS S3, SQLite, Claude API (Haiku)

**Reference design:** `docs/plans/2026-03-06-zoom-companion-design.md`

---

## Project Structure

```
zoom-companionship/
├── bot/                        # Python bot engine (runs on EC2)
│   ├── main.py                 # Entry point
│   ├── playwright_bot.py       # Zoom join + caption scraping
│   ├── audio_capture.py        # PulseAudio audio capture
│   ├── transcriber.py          # Speaches WebSocket client
│   ├── pipeline.py             # Orchestrates audio -> transcript -> storage
│   ├── storage.py              # S3 + SQLite operations
│   ├── ws_server.py            # WebSocket server (pushes to dashboard)
│   └── tests/
│       ├── test_playwright_bot.py
│       ├── test_transcriber.py
│       ├── test_pipeline.py
│       └── test_storage.py
├── api/                        # Node.js Lambda functions
│   ├── handlers/
│   │   ├── meetings.js         # CRUD for meetings
│   │   └── bot.js              # Start/stop bot
│   ├── db.js                   # SQLite wrapper
│   └── tests/
│       └── meetings.test.js
├── dashboard/                  # Next.js app
│   ├── app/
│   │   ├── page.tsx            # Meetings list
│   │   ├── meetings/
│   │   │   ├── new/page.tsx    # Start new meeting
│   │   │   └── [id]/page.tsx   # Live transcript / summary
│   │   └── layout.tsx
│   └── components/
│       ├── TranscriptView.tsx
│       ├── SummaryView.tsx
│       └── MeetingCard.tsx
├── docker/
│   ├── bot/Dockerfile
│   └── docker-compose.yml      # Speaches + bot
├── infra/
│   └── setup.sh                # EC2 bootstrap script
└── docs/plans/
```

---

## Task 1: Project Scaffolding

**Files:**
- Create: `bot/requirements.txt`
- Create: `api/package.json`
- Create: `dashboard/` (Next.js init)
- Create: `docker/docker-compose.yml`

**Step 1: Initialize bot Python environment**

```bash
cd /path/to/zoom-companionship
python3 -m venv bot/.venv
source bot/.venv/bin/activate
```

**Step 2: Create bot/requirements.txt**

```
playwright==1.44.0
websockets==12.0
boto3==1.34.0
anthropic==0.28.0
pytest==8.2.0
pytest-asyncio==0.23.0
python-dotenv==1.0.0
aiofiles==23.2.1
```

**Step 3: Install dependencies**

```bash
pip install -r bot/requirements.txt
playwright install chromium
playwright install-deps chromium
```

**Step 4: Initialize Next.js dashboard**

```bash
npx create-next-app@latest dashboard --typescript --tailwind --app --no-src-dir --import-alias "@/*"
```

**Step 5: Initialize API**

```bash
mkdir -p api/handlers
cd api && npm init -y
npm install better-sqlite3 aws-sdk @anthropic-ai/sdk
npm install --save-dev jest
```

**Step 6: Create .env file**

```bash
cat > .env << 'EOF'
AWS_REGION=us-east-1
AWS_S3_BUCKET=zoom-companion-transcripts
ANTHROPIC_API_KEY=sk-ant-...
SPEACHES_URL=ws://localhost:8000/v1/audio/transcriptions
BOT_WS_PORT=8765
EOF
```

**Step 7: Commit**

```bash
git init
git add .
git commit -m "chore: initial project scaffolding"
```

---

## Task 2: Speaches Docker Setup

**Goal:** Get Speaches (self-hosted faster-whisper) running locally, confirm it transcribes audio.

**Files:**
- Create: `docker/docker-compose.yml`
- Create: `docker/bot/Dockerfile`

**Step 1: Write docker-compose.yml**

```yaml
# docker/docker-compose.yml
version: "3.9"

services:
  speaches:
    image: ghcr.io/speaches-ai/speaches:latest-cuda
    ports:
      - "8000:8000"
    environment:
      - DEFAULT_MODEL=Systran/faster-whisper-large-v3-turbo
      - WHISPER__MODEL=Systran/faster-whisper-large-v3-turbo
    volumes:
      - speaches-models:/root/.cache/huggingface
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
    restart: unless-stopped

volumes:
  speaches-models:
```

**Step 2: Pull and start Speaches**

```bash
cd docker
docker compose up speaches -d
# Wait ~2 min for model download on first run
docker compose logs -f speaches
# Expected: "Application startup complete"
```

**Step 3: Smoke test Speaches with curl**

```bash
# Record a short test audio or use sample
curl -X POST http://localhost:8000/v1/audio/transcriptions \
  -H "Content-Type: multipart/form-data" \
  -F "file=@/path/to/test.wav" \
  -F "model=Systran/faster-whisper-large-v3-turbo" \
  -F "language=tr"
# Expected: {"text": "..."} JSON response
```

**Step 4: Commit**

```bash
git add docker/
git commit -m "feat: add Speaches Docker setup for self-hosted STT"
```

---

## Task 3: Transcriber Module

**Files:**
- Create: `bot/transcriber.py`
- Create: `bot/tests/test_transcriber.py`

**Step 1: Write failing test**

```python
# bot/tests/test_transcriber.py
import pytest
import asyncio
from unittest.mock import AsyncMock, patch
from bot.transcriber import Transcriber

@pytest.mark.asyncio
async def test_transcriber_sends_audio_and_returns_text():
    """Transcriber should send audio chunks and yield transcript segments."""
    transcriber = Transcriber(url="ws://localhost:8000/v1/audio/transcriptions")

    fake_audio_chunk = b"\x00" * 3200  # 100ms of silence at 16kHz 16-bit mono

    segments = []
    async def collect(chunk):
        async for segment in transcriber.transcribe_chunk(chunk):
            segments.append(segment)

    with patch.object(transcriber, "_send_to_speaches", new_callable=AsyncMock) as mock_send:
        mock_send.return_value = {"text": "merhaba", "language": "tr"}
        async for segment in transcriber.transcribe_chunk(fake_audio_chunk):
            segments.append(segment)

    assert len(segments) > 0
    assert segments[0]["text"] == "merhaba"
    assert segments[0]["language"] == "tr"
```

**Step 2: Run test to confirm failure**

```bash
cd bot && python -m pytest tests/test_transcriber.py -v
# Expected: FAIL - "cannot import name 'Transcriber'"
```

**Step 3: Implement transcriber.py**

```python
# bot/transcriber.py
import asyncio
import json
import httpx
from typing import AsyncGenerator

class Transcriber:
    def __init__(self, url: str = "http://localhost:8000"):
        self.base_url = url
        self._buffer = bytearray()
        self._buffer_duration_ms = 0
        self.chunk_ms = 2000  # send 2s chunks to Speaches

    async def transcribe_chunk(self, audio_bytes: bytes) -> AsyncGenerator[dict, None]:
        """Send audio bytes to Speaches, yield transcript segment."""
        self._buffer.extend(audio_bytes)
        self._buffer_duration_ms += len(audio_bytes) / 32  # 16kHz 16-bit mono = 32 bytes/ms

        if self._buffer_duration_ms >= self.chunk_ms:
            chunk = bytes(self._buffer)
            self._buffer.clear()
            self._buffer_duration_ms = 0

            segment = await self._send_to_speaches(chunk)
            if segment and segment.get("text", "").strip():
                yield segment

    async def _send_to_speaches(self, audio_bytes: bytes) -> dict:
        """POST raw audio to Speaches HTTP API."""
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                f"{self.base_url}/v1/audio/transcriptions",
                files={"file": ("audio.raw", audio_bytes, "audio/raw")},
                data={
                    "model": "Systran/faster-whisper-large-v3-turbo",
                    "response_format": "json",
                },
            )
            response.raise_for_status()
            return response.json()
```

**Step 4: Run test to confirm pass**

```bash
python -m pytest tests/test_transcriber.py -v
# Expected: PASS
```

**Step 5: Commit**

```bash
git add bot/transcriber.py bot/tests/test_transcriber.py
git commit -m "feat: add Transcriber module for Speaches STT integration"
```

---

## Task 4: Storage Module

**Files:**
- Create: `bot/storage.py`
- Create: `bot/tests/test_storage.py`

**Step 1: Write failing tests**

```python
# bot/tests/test_storage.py
import pytest
import tempfile
import os
from unittest.mock import patch, MagicMock
from bot.storage import Storage

@pytest.fixture
def storage(tmp_path):
    db_path = str(tmp_path / "test.db")
    return Storage(db_path=db_path, s3_bucket="test-bucket", local_dir=str(tmp_path))

def test_create_meeting(storage):
    meeting_id = storage.create_meeting(
        title="Weekly Sync",
        platform="zoom",
        meeting_url="https://zoom.us/j/123"
    )
    assert meeting_id is not None
    meeting = storage.get_meeting(meeting_id)
    assert meeting["title"] == "Weekly Sync"
    assert meeting["status"] == "ongoing"

def test_append_transcript_segment(storage):
    meeting_id = storage.create_meeting("Test", "zoom", "https://zoom.us/j/1")
    storage.append_segment(meeting_id, speaker="Barbaros", text="Merhaba", timestamp="00:00:05")
    segments = storage.get_segments(meeting_id)
    assert len(segments) == 1
    assert segments[0]["speaker"] == "Barbaros"
    assert segments[0]["text"] == "Merhaba"

def test_complete_meeting(storage):
    meeting_id = storage.create_meeting("Test", "zoom", "https://zoom.us/j/1")
    storage.complete_meeting(meeting_id, summary="Test summary", action_items=["Do X", "Do Y"])
    meeting = storage.get_meeting(meeting_id)
    assert meeting["status"] == "completed"
    assert meeting["summary"] == "Test summary"
```

**Step 2: Run tests to confirm failure**

```bash
python -m pytest tests/test_storage.py -v
# Expected: FAIL
```

**Step 3: Implement storage.py**

```python
# bot/storage.py
import sqlite3
import json
import os
from datetime import datetime
from pathlib import Path

class Storage:
    def __init__(self, db_path: str, s3_bucket: str, local_dir: str):
        self.db_path = db_path
        self.s3_bucket = s3_bucket
        self.local_dir = Path(local_dir)
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
                    duration_sec INTEGER DEFAULT 0,
                    participants TEXT DEFAULT '[]',
                    status TEXT DEFAULT 'ongoing',
                    summary TEXT,
                    action_items TEXT DEFAULT '[]',
                    transcript_path TEXT
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
        import uuid
        meeting_id = str(uuid.uuid4())[:8]
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO meetings (id, title, platform, meeting_url, date) VALUES (?,?,?,?,?)",
                (meeting_id, title, platform, meeting_url, datetime.utcnow().isoformat())
            )
        return meeting_id

    def get_meeting(self, meeting_id: str) -> dict:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT * FROM meetings WHERE id=?", (meeting_id,)).fetchone()
            return dict(row) if row else None

    def append_segment(self, meeting_id: str, speaker: str, text: str, timestamp: str):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO segments (meeting_id, speaker, text, timestamp, created_at) VALUES (?,?,?,?,?)",
                (meeting_id, speaker, text, timestamp, datetime.utcnow().isoformat())
            )
        # Also append to local transcript file
        transcript_file = self.local_dir / f"{meeting_id}_transcript.md"
        with open(transcript_file, "a") as f:
            f.write(f"[{timestamp}] **{speaker}:** {text}\n\n")

    def get_segments(self, meeting_id: str) -> list:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM segments WHERE meeting_id=? ORDER BY id", (meeting_id,)
            ).fetchall()
            return [dict(r) for r in rows]

    def complete_meeting(self, meeting_id: str, summary: str, action_items: list):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE meetings SET status=?, summary=?, action_items=? WHERE id=?",
                ("completed", summary, json.dumps(action_items), meeting_id)
            )
```

**Step 4: Run tests**

```bash
python -m pytest tests/test_storage.py -v
# Expected: PASS all 3 tests
```

**Step 5: Commit**

```bash
git add bot/storage.py bot/tests/test_storage.py
git commit -m "feat: add Storage module for SQLite + local transcript files"
```

---

## Task 5: Playwright Bot — Zoom Join

**Files:**
- Create: `bot/playwright_bot.py`
- Create: `bot/tests/test_playwright_bot.py`

**Step 1: Write failing test (mocked)**

```python
# bot/tests/test_playwright_bot.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import asyncio

@pytest.mark.asyncio
async def test_bot_joins_meeting():
    """Bot should navigate to meeting URL and click join."""
    from bot.playwright_bot import ZoomBot

    bot = ZoomBot(display_name="Companion")

    with patch("bot.playwright_bot.async_playwright") as mock_pw:
        mock_browser = AsyncMock()
        mock_page = AsyncMock()
        mock_pw.return_value.__aenter__.return_value.chromium.launch.return_value = mock_browser
        mock_browser.new_context.return_value.new_page.return_value = mock_page
        mock_page.title.return_value = "Zoom Meeting"

        await bot.join("https://zoom.us/wc/join/123456789?pwd=abc")

        mock_page.goto.assert_called_once()
        assert bot.is_joined is True

@pytest.mark.asyncio
async def test_bot_gets_active_speaker():
    """Bot should return current active speaker name from Zoom UI."""
    from bot.playwright_bot import ZoomBot

    bot = ZoomBot(display_name="Companion")
    bot._page = AsyncMock()
    bot._page.query_selector.return_value = AsyncMock(
        inner_text=AsyncMock(return_value="Barbaros Yahya")
    )

    speaker = await bot.get_active_speaker()
    assert speaker == "Barbaros Yahya"
```

**Step 2: Run to confirm failure**

```bash
python -m pytest tests/test_playwright_bot.py -v
# Expected: FAIL
```

**Step 3: Implement playwright_bot.py**

```python
# bot/playwright_bot.py
import asyncio
from playwright.async_api import async_playwright, Page, Browser

class ZoomBot:
    """Joins Zoom meetings via headless Chromium and scrapes captions."""

    # CSS selectors for Zoom web client (update if Zoom changes UI)
    SELECTORS = {
        "name_input": 'input[placeholder="Your Name"]',
        "join_button": 'button[data-testid="joinBtn"], button.join-btn, #joinBtn',
        "active_speaker": '.active-speaker-name, [class*="active-speaker"] .participant-name',
        "caption_text": '.caption-line, [class*="caption"] span',
    }

    def __init__(self, display_name: str = "Companion"):
        self.display_name = display_name
        self.is_joined = False
        self._browser: Browser = None
        self._page: Page = None
        self._playwright = None

    async def join(self, meeting_url: str):
        """Join a Zoom meeting via the web client."""
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--use-fake-ui-for-media-stream",  # auto-allow mic/camera
                "--use-fake-device-for-media-stream",
            ]
        )
        context = await self._browser.new_context(
            permissions=["microphone", "camera"],
            user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"
        )
        self._page = await context.new_page()

        # Convert zoom.us/j/ links to web client format
        web_url = meeting_url.replace("zoom.us/j/", "zoom.us/wc/join/")
        await self._page.goto(web_url, wait_until="networkidle", timeout=30000)

        # Enter display name
        name_input = await self._page.query_selector(self.SELECTORS["name_input"])
        if name_input:
            await name_input.fill(self.display_name)

        # Click join
        join_btn = await self._page.query_selector(self.SELECTORS["join_button"])
        if join_btn:
            await join_btn.click()

        await asyncio.sleep(3)  # wait for join animation
        self.is_joined = True

    async def get_active_speaker(self) -> str | None:
        """Scrape the currently active speaker's name from Zoom UI."""
        if not self._page:
            return None
        el = await self._page.query_selector(self.SELECTORS["active_speaker"])
        if el:
            return await el.inner_text()
        return None

    async def send_chat_message(self, message: str):
        """Send a message in the meeting chat."""
        if not self._page:
            return
        # Open chat panel
        await self._page.keyboard.press("Alt+H")
        await asyncio.sleep(0.5)
        chat_input = await self._page.query_selector('[placeholder*="message"], .chat-input textarea')
        if chat_input:
            await chat_input.fill(message)
            await self._page.keyboard.press("Enter")

    async def leave(self):
        """Leave the meeting and clean up."""
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
        self.is_joined = False
```

**Step 4: Run tests**

```bash
python -m pytest tests/test_playwright_bot.py -v
# Expected: PASS
```

**Step 5: Commit**

```bash
git add bot/playwright_bot.py bot/tests/test_playwright_bot.py
git commit -m "feat: add ZoomBot Playwright module for headless meeting join"
```

---

## Task 6: Audio Capture Module

**Goal:** Capture system audio from PulseAudio virtual sink (receives Zoom audio).

**Files:**
- Create: `bot/audio_capture.py`
- Create: `bot/tests/test_audio_capture.py`

**Step 1: Write failing test**

```python
# bot/tests/test_audio_capture.py
import pytest
from unittest.mock import patch, MagicMock
from bot.audio_capture import AudioCapture

def test_audio_capture_yields_chunks():
    """AudioCapture should yield audio bytes in configurable chunk sizes."""
    capture = AudioCapture(chunk_ms=100)
    assert capture.chunk_size_bytes == 3200  # 100ms at 16kHz 16-bit mono

def test_audio_capture_uses_pulse_monitor():
    """AudioCapture should use PulseAudio monitor source."""
    capture = AudioCapture()
    assert "monitor" in capture.source_name or capture.source_name == "default"
```

**Step 2: Run to confirm failure**

```bash
python -m pytest tests/test_audio_capture.py -v
# Expected: FAIL
```

**Step 3: Implement audio_capture.py**

```python
# bot/audio_capture.py
import asyncio
import subprocess
from typing import AsyncGenerator

# Audio config: 16kHz, 16-bit mono (what Speaches/Whisper expects)
SAMPLE_RATE = 16000
CHANNELS = 1
SAMPLE_WIDTH = 2  # 16-bit = 2 bytes

class AudioCapture:
    """Captures audio from PulseAudio virtual sink monitor."""

    def __init__(self, chunk_ms: int = 2000, source_name: str = "virtual_sink.monitor"):
        self.chunk_ms = chunk_ms
        self.source_name = source_name
        # bytes per ms = sample_rate * channels * sample_width / 1000
        self.bytes_per_ms = SAMPLE_RATE * CHANNELS * SAMPLE_WIDTH // 1000
        self.chunk_size_bytes = self.bytes_per_ms * chunk_ms
        self._process = None

    async def stream(self) -> AsyncGenerator[bytes, None]:
        """Stream audio from PulseAudio monitor source as raw PCM bytes."""
        cmd = [
            "parec",
            f"--source={self.source_name}",
            "--format=s16le",
            f"--rate={SAMPLE_RATE}",
            f"--channels={CHANNELS}",
            "--latency-msec=100",
        ]
        self._process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        buffer = bytearray()
        while True:
            chunk = await self._process.stdout.read(4096)
            if not chunk:
                break
            buffer.extend(chunk)
            while len(buffer) >= self.chunk_size_bytes:
                yield bytes(buffer[:self.chunk_size_bytes])
                buffer = buffer[self.chunk_size_bytes:]

    async def stop(self):
        if self._process:
            self._process.terminate()
            await self._process.wait()
```

**Step 4: Run tests**

```bash
python -m pytest tests/test_audio_capture.py -v
# Expected: PASS
```

**Step 5: Setup PulseAudio virtual sink (run on EC2)**

```bash
# Create virtual audio sink that Zoom audio will route through
pactl load-module module-null-sink sink_name=virtual_sink sink_properties=device.description=VirtualSink
pactl set-default-sink virtual_sink
# Zoom web audio will now go to virtual_sink
# parec reads from virtual_sink.monitor
```

**Step 6: Commit**

```bash
git add bot/audio_capture.py bot/tests/test_audio_capture.py
git commit -m "feat: add AudioCapture module for PulseAudio virtual sink streaming"
```

---

## Task 7: Transcript Pipeline

**Goal:** Wire AudioCapture + Transcriber + ZoomBot caption scraping into a unified pipeline that emits `{speaker, text, timestamp}` events.

**Files:**
- Create: `bot/pipeline.py`
- Create: `bot/tests/test_pipeline.py`

**Step 1: Write failing test**

```python
# bot/tests/test_pipeline.py
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

@pytest.mark.asyncio
async def test_pipeline_emits_transcript_segments():
    """Pipeline should combine audio, STT, and speaker to emit segments."""
    from bot.pipeline import TranscriptPipeline

    mock_bot = MagicMock()
    mock_bot.get_active_speaker = AsyncMock(return_value="Barbaros")

    mock_transcriber = MagicMock()
    async def fake_transcribe(chunk):
        yield {"text": "Merhaba dünya", "language": "tr"}
    mock_transcriber.transcribe_chunk = fake_transcribe

    mock_audio = MagicMock()
    async def fake_stream():
        yield b"\x00" * 3200
    mock_audio.stream = fake_stream

    pipeline = TranscriptPipeline(bot=mock_bot, transcriber=mock_transcriber, audio=mock_audio)

    segments = []
    async for segment in pipeline.run(meeting_id="test123", max_chunks=1):
        segments.append(segment)

    assert len(segments) == 1
    assert segments[0]["speaker"] == "Barbaros"
    assert segments[0]["text"] == "Merhaba dünya"
    assert "timestamp" in segments[0]
    assert segments[0]["meeting_id"] == "test123"
```

**Step 2: Run to confirm failure**

```bash
python -m pytest tests/test_pipeline.py -v
# Expected: FAIL
```

**Step 3: Implement pipeline.py**

```python
# bot/pipeline.py
import asyncio
from datetime import datetime, timedelta
from typing import AsyncGenerator

class TranscriptPipeline:
    """Orchestrates audio capture -> STT -> speaker tagging -> segment emission."""

    def __init__(self, bot, transcriber, audio):
        self.bot = bot
        self.transcriber = transcriber
        self.audio = audio
        self._start_time = None

    def _elapsed_timestamp(self) -> str:
        if not self._start_time:
            return "00:00:00"
        elapsed = datetime.utcnow() - self._start_time
        total_seconds = int(elapsed.total_seconds())
        h, remainder = divmod(total_seconds, 3600)
        m, s = divmod(remainder, 60)
        return f"{h:02d}:{m:02d}:{s:02d}"

    async def run(self, meeting_id: str, max_chunks: int = None) -> AsyncGenerator[dict, None]:
        """Stream transcript segments for a meeting."""
        self._start_time = datetime.utcnow()
        chunks_processed = 0

        async for audio_chunk in self.audio.stream():
            speaker = await self.bot.get_active_speaker() or "Unknown"
            timestamp = self._elapsed_timestamp()

            async for segment in self.transcriber.transcribe_chunk(audio_chunk):
                if segment.get("text", "").strip():
                    yield {
                        "meeting_id": meeting_id,
                        "speaker": speaker,
                        "text": segment["text"].strip(),
                        "language": segment.get("language", "unknown"),
                        "timestamp": timestamp,
                    }

            chunks_processed += 1
            if max_chunks and chunks_processed >= max_chunks:
                break
```

**Step 4: Run tests**

```bash
python -m pytest tests/test_pipeline.py -v
# Expected: PASS
```

**Step 5: Commit**

```bash
git add bot/pipeline.py bot/tests/test_pipeline.py
git commit -m "feat: add TranscriptPipeline orchestrating audio, STT, and speaker tagging"
```

---

## Task 8: WebSocket Server (Live Dashboard Push)

**Goal:** Push transcript segments to the dashboard in real-time via WebSocket.

**Files:**
- Create: `bot/ws_server.py`
- Create: `bot/tests/test_ws_server.py`

**Step 1: Write failing test**

```python
# bot/tests/test_ws_server.py
import pytest
import asyncio
import json
import websockets
from bot.ws_server import TranscriptWSServer

@pytest.mark.asyncio
async def test_ws_server_broadcasts_segment():
    """Server should broadcast segments to connected clients."""
    server = TranscriptWSServer(port=8766)
    await server.start()

    received = []
    async with websockets.connect("ws://localhost:8766") as ws:
        await server.broadcast({
            "meeting_id": "abc123",
            "speaker": "Barbaros",
            "text": "Test mesaj",
            "timestamp": "00:01:00",
        })
        msg = await asyncio.wait_for(ws.recv(), timeout=2)
        received.append(json.loads(msg))

    await server.stop()
    assert received[0]["speaker"] == "Barbaros"
    assert received[0]["text"] == "Test mesaj"
```

**Step 2: Run to confirm failure**

```bash
python -m pytest tests/test_ws_server.py -v
```

**Step 3: Implement ws_server.py**

```python
# bot/ws_server.py
import asyncio
import json
import websockets
from websockets.server import WebSocketServerProtocol

class TranscriptWSServer:
    """WebSocket server that broadcasts transcript segments to dashboard clients."""

    def __init__(self, port: int = 8765):
        self.port = port
        self._clients: set[WebSocketServerProtocol] = set()
        self._server = None

    async def _handler(self, websocket: WebSocketServerProtocol):
        self._clients.add(websocket)
        try:
            await websocket.wait_closed()
        finally:
            self._clients.discard(websocket)

    async def start(self):
        self._server = await websockets.serve(self._handler, "0.0.0.0", self.port)

    async def stop(self):
        if self._server:
            self._server.close()
            await self._server.wait_closed()

    async def broadcast(self, segment: dict):
        """Send a transcript segment to all connected dashboard clients."""
        if not self._clients:
            return
        message = json.dumps(segment)
        await asyncio.gather(
            *[client.send(message) for client in self._clients],
            return_exceptions=True
        )
```

**Step 4: Run tests**

```bash
python -m pytest tests/test_ws_server.py -v
# Expected: PASS
```

**Step 5: Commit**

```bash
git add bot/ws_server.py bot/tests/test_ws_server.py
git commit -m "feat: add WebSocket server for real-time transcript push to dashboard"
```

---

## Task 9: Summary Generation (Claude API)

**Files:**
- Create: `bot/summarizer.py`
- Create: `bot/tests/test_summarizer.py`

**Step 1: Write failing test**

```python
# bot/tests/test_summarizer.py
import pytest
from unittest.mock import MagicMock, patch

def test_summarizer_returns_summary_and_action_items():
    from bot.summarizer import Summarizer

    fake_transcript = """
[00:00:10] **Barbaros:** Bu sprint için hedeflerimizi konuşalım.
[00:00:20] **Ahmet:** Auth modülünü bitirmem gerekiyor.
[00:00:35] **Barbaros:** Tamam, Ahmet auth'u bitirecek. Ben dashboard'u alıyorum.
"""
    summarizer = Summarizer(api_key="fake-key")

    mock_response = MagicMock()
    mock_response.content = [MagicMock(text='{"summary": ["Sprint hedefleri konuşuldu"], "action_items": ["Ahmet: auth modülünü bitir", "Barbaros: dashboard yap"]}')]

    with patch.object(summarizer._client.messages, "create", return_value=mock_response):
        result = summarizer.generate(transcript=fake_transcript, participants=["Barbaros", "Ahmet"])

    assert "summary" in result
    assert "action_items" in result
    assert len(result["action_items"]) >= 1
```

**Step 2: Run to confirm failure**

```bash
python -m pytest tests/test_summarizer.py -v
```

**Step 3: Implement summarizer.py**

```python
# bot/summarizer.py
import json
import anthropic

SYSTEM_PROMPT = """You are a meeting assistant. Given a meeting transcript, extract:
1. A bullet-point summary (5-10 key points)
2. Action items with owner names

Return ONLY valid JSON in this format:
{
  "summary": ["point 1", "point 2", ...],
  "action_items": ["Owner: action", ...]
}"""

class Summarizer:
    def __init__(self, api_key: str):
        self._client = anthropic.Anthropic(api_key=api_key)

    def generate(self, transcript: str, participants: list[str]) -> dict:
        """Generate summary and action items from meeting transcript."""
        user_message = f"""Participants: {', '.join(participants)}

Transcript:
{transcript}

Extract summary and action items as JSON."""

        response = self._client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
        )

        text = response.content[0].text
        # Extract JSON from response
        start = text.find("{")
        end = text.rfind("}") + 1
        return json.loads(text[start:end])
```

**Step 4: Run tests**

```bash
python -m pytest tests/test_summarizer.py -v
# Expected: PASS
```

**Step 5: Commit**

```bash
git add bot/summarizer.py bot/tests/test_summarizer.py
git commit -m "feat: add Summarizer using Claude Haiku for post-meeting summaries"
```

---

## Task 10: Bot Main Entry Point

**Files:**
- Create: `bot/main.py`

**Step 1: Implement main.py**

```python
# bot/main.py
"""
Entry point for the Zoom Companion bot.
Called by Lambda/API when a meeting starts.

Usage:
  python main.py --meeting-url "https://zoom.us/j/123" --meeting-id "abc123"
"""
import asyncio
import argparse
import os
from dotenv import load_dotenv

from bot.playwright_bot import ZoomBot
from bot.audio_capture import AudioCapture
from bot.transcriber import Transcriber
from bot.pipeline import TranscriptPipeline
from bot.ws_server import TranscriptWSServer
from bot.storage import Storage
from bot.summarizer import Summarizer

load_dotenv()

async def run_meeting(meeting_url: str, meeting_id: str):
    # Init components
    storage = Storage(
        db_path=os.getenv("DB_PATH", "/data/meetings.db"),
        s3_bucket=os.getenv("AWS_S3_BUCKET"),
        local_dir="/data/transcripts",
    )
    ws_server = TranscriptWSServer(port=int(os.getenv("BOT_WS_PORT", 8765)))
    bot = ZoomBot(display_name=os.getenv("BOT_NAME", "Companion"))
    audio = AudioCapture()
    transcriber = Transcriber(url=os.getenv("SPEACHES_URL", "http://localhost:8000"))
    pipeline = TranscriptPipeline(bot=bot, transcriber=transcriber, audio=audio)
    summarizer = Summarizer(api_key=os.getenv("ANTHROPIC_API_KEY"))

    # Start WebSocket server
    await ws_server.start()
    print(f"WS server started on port {os.getenv('BOT_WS_PORT', 8765)}")

    # Join meeting
    await bot.join(meeting_url)
    await bot.send_chat_message("Transcription started ✅")
    print(f"Bot joined: {meeting_url}")

    # Stream transcript
    participants = set()
    async for segment in pipeline.run(meeting_id=meeting_id):
        participants.add(segment["speaker"])
        storage.append_segment(
            meeting_id=meeting_id,
            speaker=segment["speaker"],
            text=segment["text"],
            timestamp=segment["timestamp"],
        )
        await ws_server.broadcast(segment)
        print(f"[{segment['timestamp']}] {segment['speaker']}: {segment['text']}")

    # Meeting ended - generate summary
    print("Meeting ended, generating summary...")
    segments = storage.get_segments(meeting_id)
    transcript_text = "\n".join(
        f"[{s['timestamp']}] **{s['speaker']}:** {s['text']}" for s in segments
    )
    result = summarizer.generate(transcript=transcript_text, participants=list(participants))
    storage.complete_meeting(
        meeting_id=meeting_id,
        summary="\n".join(result["summary"]),
        action_items=result["action_items"],
    )
    print("Summary saved.")
    await bot.leave()
    await ws_server.stop()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--meeting-url", required=True)
    parser.add_argument("--meeting-id", required=True)
    args = parser.parse_args()
    asyncio.run(run_meeting(args.meeting_url, args.meeting_id))
```

**Step 2: Test manually with a Zoom test meeting**

```bash
source bot/.venv/bin/activate
python bot/main.py --meeting-url "https://zoom.us/j/YOUR_TEST_MEETING" --meeting-id "test001"
# Expected: Bot joins, you see transcript in terminal
```

**Step 3: Commit**

```bash
git add bot/main.py
git commit -m "feat: add bot main entry point wiring all components"
```

---

## Task 11: Lambda API

**Files:**
- Create: `api/handlers/meetings.js`
- Create: `api/handlers/bot.js`
- Create: `api/db.js`
- Create: `api/tests/meetings.test.js`

**Step 1: Write failing test**

```javascript
// api/tests/meetings.test.js
const { handler } = require('../handlers/meetings');

describe('GET /meetings', () => {
  it('returns list of meetings', async () => {
    const event = { httpMethod: 'GET', path: '/meetings' };
    const result = await handler(event);
    expect(result.statusCode).toBe(200);
    const body = JSON.parse(result.body);
    expect(Array.isArray(body)).toBe(true);
  });
});

describe('POST /meetings', () => {
  it('creates a new meeting and returns meeting_id', async () => {
    const event = {
      httpMethod: 'POST',
      path: '/meetings',
      body: JSON.stringify({ meeting_url: 'https://zoom.us/j/123', title: 'Test' }),
    };
    const result = await handler(event);
    expect(result.statusCode).toBe(201);
    const body = JSON.parse(result.body);
    expect(body.meeting_id).toBeDefined();
  });
});
```

**Step 2: Run to confirm failure**

```bash
cd api && npx jest tests/meetings.test.js
# Expected: FAIL
```

**Step 3: Implement api/db.js**

```javascript
// api/db.js
const Database = require('better-sqlite3');
const path = require('path');

const DB_PATH = process.env.DB_PATH || path.join(__dirname, '../data/meetings.db');

let _db;
function getDb() {
  if (!_db) {
    _db = new Database(DB_PATH);
    _db.exec(`
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
    `);
  }
  return _db;
}

module.exports = { getDb };
```

**Step 4: Implement api/handlers/meetings.js**

```javascript
// api/handlers/meetings.js
const { getDb } = require('../db');
const { v4: uuidv4 } = require('uuid');

exports.handler = async (event) => {
  const db = getDb();
  const method = event.httpMethod;

  if (method === 'GET') {
    const meetings = db.prepare('SELECT * FROM meetings ORDER BY date DESC').all();
    return { statusCode: 200, body: JSON.stringify(meetings) };
  }

  if (method === 'POST') {
    const { meeting_url, title = 'Meeting' } = JSON.parse(event.body || '{}');
    if (!meeting_url) {
      return { statusCode: 400, body: JSON.stringify({ error: 'meeting_url required' }) };
    }
    const id = uuidv4().slice(0, 8);
    db.prepare(
      'INSERT INTO meetings (id, title, meeting_url, platform, date) VALUES (?, ?, ?, ?, ?)'
    ).run(id, title, meeting_url, 'zoom', new Date().toISOString());

    return { statusCode: 201, body: JSON.stringify({ meeting_id: id }) };
  }

  return { statusCode: 405, body: JSON.stringify({ error: 'Method not allowed' }) };
};
```

**Step 5: Run tests**

```bash
cd api && npx jest tests/meetings.test.js
# Expected: PASS
```

**Step 6: Commit**

```bash
git add api/
git commit -m "feat: add Lambda API handlers for meetings CRUD"
```

---

## Task 12: Next.js Dashboard

**Files:**
- Modify: `dashboard/app/page.tsx`
- Create: `dashboard/app/meetings/new/page.tsx`
- Create: `dashboard/app/meetings/[id]/page.tsx`
- Create: `dashboard/components/TranscriptView.tsx`
- Create: `dashboard/components/SummaryView.tsx`
- Create: `dashboard/components/MeetingCard.tsx`

**Step 1: Create MeetingCard component**

```typescript
// dashboard/components/MeetingCard.tsx
import Link from 'next/link';

interface Meeting {
  id: string;
  title: string;
  date: string;
  status: 'ongoing' | 'completed';
  participants: string;
}

export function MeetingCard({ meeting }: { meeting: Meeting }) {
  return (
    <Link href={`/meetings/${meeting.id}`}>
      <div className="border rounded-lg p-4 hover:bg-gray-50 cursor-pointer">
        <div className="flex justify-between items-start">
          <h3 className="font-medium">{meeting.title}</h3>
          <span className={`text-xs px-2 py-1 rounded-full ${
            meeting.status === 'ongoing'
              ? 'bg-green-100 text-green-700'
              : 'bg-gray-100 text-gray-600'
          }`}>
            {meeting.status === 'ongoing' ? 'Live' : 'Completed'}
          </span>
        </div>
        <p className="text-sm text-gray-500 mt-1">
          {new Date(meeting.date).toLocaleString()}
        </p>
        {meeting.participants && (
          <p className="text-sm text-gray-400 mt-1">
            {JSON.parse(meeting.participants).join(', ')}
          </p>
        )}
      </div>
    </Link>
  );
}
```

**Step 2: Create TranscriptView component**

```typescript
// dashboard/components/TranscriptView.tsx
'use client';
import { useEffect, useRef, useState } from 'react';

interface Segment {
  speaker: string;
  text: string;
  timestamp: string;
}

interface Props {
  meetingId: string;
  initialSegments: Segment[];
  isLive: boolean;
}

export function TranscriptView({ meetingId, initialSegments, isLive }: Props) {
  const [segments, setSegments] = useState<Segment[]>(initialSegments);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!isLive) return;
    const ws = new WebSocket(
      process.env.NEXT_PUBLIC_BOT_WS_URL || 'ws://localhost:8765'
    );
    ws.onmessage = (event) => {
      const segment = JSON.parse(event.data);
      if (segment.meeting_id === meetingId) {
        setSegments((prev) => [...prev, segment]);
      }
    };
    return () => ws.close();
  }, [meetingId, isLive]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [segments]);

  return (
    <div className="space-y-3 max-h-[600px] overflow-y-auto p-4">
      {segments.map((seg, i) => (
        <div key={i} className="flex gap-3">
          <span className="text-xs text-gray-400 w-16 shrink-0 pt-1">{seg.timestamp}</span>
          <div>
            <span className="font-semibold text-sm">{seg.speaker}: </span>
            <span className="text-sm">{seg.text}</span>
          </div>
        </div>
      ))}
      {isLive && (
        <div className="flex items-center gap-2 text-green-600 text-sm">
          <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
          Live transcription active
        </div>
      )}
      <div ref={bottomRef} />
    </div>
  );
}
```

**Step 3: Create meetings list page**

```typescript
// dashboard/app/page.tsx
import { MeetingCard } from '@/components/MeetingCard';
import Link from 'next/link';

async function getMeetings() {
  const res = await fetch(`${process.env.API_URL}/meetings`, { cache: 'no-store' });
  if (!res.ok) return [];
  return res.json();
}

export default async function Home() {
  const meetings = await getMeetings();
  return (
    <main className="max-w-2xl mx-auto p-6">
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl font-bold">Meetings</h1>
        <Link href="/meetings/new" className="bg-blue-600 text-white px-4 py-2 rounded-lg text-sm">
          + New Meeting
        </Link>
      </div>
      <div className="space-y-3">
        {meetings.length === 0 && (
          <p className="text-gray-500 text-center py-12">No meetings yet.</p>
        )}
        {meetings.map((m: any) => (
          <MeetingCard key={m.id} meeting={m} />
        ))}
      </div>
    </main>
  );
}
```

**Step 4: Create new meeting page**

```typescript
// dashboard/app/meetings/new/page.tsx
'use client';
import { useState } from 'react';
import { useRouter } from 'next/navigation';

export default function NewMeeting() {
  const [url, setUrl] = useState('');
  const [title, setTitle] = useState('');
  const [loading, setLoading] = useState(false);
  const router = useRouter();

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    const res = await fetch('/api/start-meeting', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ meeting_url: url, title }),
    });
    const { meeting_id } = await res.json();
    router.push(`/meetings/${meeting_id}`);
  }

  return (
    <main className="max-w-lg mx-auto p-6">
      <h1 className="text-2xl font-bold mb-6">Start New Meeting</h1>
      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label className="block text-sm font-medium mb-1">Meeting Title</label>
          <input
            className="w-full border rounded-lg px-3 py-2"
            value={title}
            onChange={e => setTitle(e.target.value)}
            placeholder="Weekly Sync"
          />
        </div>
        <div>
          <label className="block text-sm font-medium mb-1">Zoom Meeting URL</label>
          <input
            className="w-full border rounded-lg px-3 py-2"
            value={url}
            onChange={e => setUrl(e.target.value)}
            placeholder="https://zoom.us/j/..."
            required
          />
        </div>
        <button
          type="submit"
          disabled={loading}
          className="w-full bg-blue-600 text-white py-2 rounded-lg disabled:opacity-50"
        >
          {loading ? 'Starting bot...' : 'Start Companion'}
        </button>
      </form>
    </main>
  );
}
```

**Step 5: Create meeting detail page**

```typescript
// dashboard/app/meetings/[id]/page.tsx
import { TranscriptView } from '@/components/TranscriptView';

async function getMeeting(id: string) {
  const res = await fetch(`${process.env.API_URL}/meetings/${id}`, { cache: 'no-store' });
  return res.json();
}

export default async function MeetingPage({ params }: { params: { id: string } }) {
  const meeting = await getMeeting(params.id);
  const isLive = meeting.status === 'ongoing';

  return (
    <main className="max-w-3xl mx-auto p-6">
      <div className="flex justify-between items-center mb-4">
        <h1 className="text-xl font-bold">{meeting.title}</h1>
        <span className={`text-sm px-3 py-1 rounded-full ${
          isLive ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-600'
        }`}>
          {isLive ? 'Live' : 'Completed'}
        </span>
      </div>

      <div className="border rounded-lg">
        <TranscriptView
          meetingId={params.id}
          initialSegments={meeting.segments || []}
          isLive={isLive}
        />
      </div>

      {!isLive && meeting.summary && (
        <div className="mt-6 border rounded-lg p-4">
          <h2 className="font-bold mb-3">Summary</h2>
          <ul className="space-y-2">
            {meeting.summary.split('\n').map((point: string, i: number) => (
              <li key={i} className="text-sm flex gap-2">
                <span>•</span> {point}
              </li>
            ))}
          </ul>
          {meeting.action_items && (
            <>
              <h2 className="font-bold mt-4 mb-3">Action Items</h2>
              <ul className="space-y-2">
                {JSON.parse(meeting.action_items).map((item: string, i: number) => (
                  <li key={i} className="text-sm flex gap-2">
                    <span>☐</span> {item}
                  </li>
                ))}
              </ul>
            </>
          )}
        </div>
      )}
    </main>
  );
}
```

**Step 6: Commit**

```bash
git add dashboard/
git commit -m "feat: add Next.js dashboard with meetings list, live transcript, and summary views"
```

---

## Task 13: Docker Compose & EC2 Setup

**Files:**
- Create: `docker/bot/Dockerfile`
- Update: `docker/docker-compose.yml`
- Create: `infra/setup.sh`

**Step 1: Create bot Dockerfile**

```dockerfile
# docker/bot/Dockerfile
FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    pulseaudio \
    pulseaudio-utils \
    chromium \
    chromium-driver \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY bot/requirements.txt .
RUN pip install -r requirements.txt
RUN playwright install chromium
RUN playwright install-deps chromium

COPY bot/ ./bot/
COPY .env .

CMD ["python", "bot/main.py"]
```

**Step 2: Update docker-compose.yml**

```yaml
# docker/docker-compose.yml
version: "3.9"

services:
  speaches:
    image: ghcr.io/speaches-ai/speaches:latest-cuda
    ports:
      - "8000:8000"
    environment:
      - DEFAULT_MODEL=Systran/faster-whisper-large-v3-turbo
    volumes:
      - speaches-models:/root/.cache/huggingface
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
    restart: unless-stopped

  bot:
    build:
      context: ..
      dockerfile: docker/bot/Dockerfile
    depends_on:
      - speaches
    environment:
      - SPEACHES_URL=http://speaches:8000
    volumes:
      - /data:/data
    network_mode: host
    restart: unless-stopped

volumes:
  speaches-models:
```

**Step 3: Create EC2 bootstrap script**

```bash
#!/bin/bash
# infra/setup.sh
# Run once on fresh EC2 g4dn.xlarge Ubuntu 22.04

set -e

# NVIDIA drivers + CUDA
apt-get update
apt-get install -y nvidia-driver-525 nvidia-cuda-toolkit

# Docker + NVIDIA container toolkit
curl -fsSL https://get.docker.com | sh
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | apt-key add -
curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | \
  tee /etc/apt/sources.list.d/nvidia-docker.list
apt-get update && apt-get install -y nvidia-container-toolkit
systemctl restart docker

# PulseAudio virtual sink
apt-get install -y pulseaudio pulseaudio-utils
pulseaudio --start
pactl load-module module-null-sink sink_name=virtual_sink
pactl set-default-sink virtual_sink

# Clone repo and start services
cd /opt
git clone https://github.com/YOUR_REPO/zoom-companionship.git
cd zoom-companionship
cp .env.example .env  # fill in API keys

cd docker
docker compose up -d

echo "Setup complete. Bot ready."
```

**Step 4: Commit**

```bash
git add docker/ infra/
git commit -m "feat: add Docker setup and EC2 bootstrap script"
```

---

## Task 14: End-to-End Smoke Test

**Goal:** Verify the full pipeline works in a controlled test.

**Step 1: Start all services**

```bash
cd docker && docker compose up -d
# Verify: docker compose ps -> all services "Up"
```

**Step 2: Start dashboard**

```bash
cd dashboard && npm run dev
# Open http://localhost:3000
```

**Step 3: Run bot against a test Zoom meeting**

```bash
source bot/.venv/bin/activate
python bot/main.py \
  --meeting-url "https://zoom.us/j/YOUR_TEST_MEETING_ID" \
  --meeting-id "smoke-test-001"
```

**Expected output:**
```
WS server started on port 8765
Bot joined: https://zoom.us/j/...
[00:00:05] Unknown: ...
[00:00:08] Barbaros: ...
Meeting ended, generating summary...
Summary saved.
```

**Step 4: Verify dashboard shows transcript**

Open `http://localhost:3000` → click the meeting → should see live transcript segments appearing.

**Step 5: Verify summary**

After meeting ends, refresh the meeting page → summary and action items should appear.

**Step 6: Final commit**

```bash
git add .
git commit -m "chore: end-to-end smoke test verified, Phase 1 complete"
```

---

## Summary

| Task | Component | Status |
|------|-----------|--------|
| 1 | Project scaffolding | [ ] |
| 2 | Speaches Docker | [ ] |
| 3 | Transcriber module | [ ] |
| 4 | Storage module | [ ] |
| 5 | Playwright bot | [ ] |
| 6 | Audio capture | [ ] |
| 7 | Transcript pipeline | [ ] |
| 8 | WebSocket server | [ ] |
| 9 | Summarizer (Claude) | [ ] |
| 10 | Bot main entry point | [ ] |
| 11 | Lambda API | [ ] |
| 12 | Next.js dashboard | [ ] |
| 13 | Docker + EC2 setup | [ ] |
| 14 | End-to-end smoke test | [ ] |
