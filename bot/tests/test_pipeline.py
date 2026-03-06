# bot/tests/test_pipeline.py
import pytest
from unittest.mock import AsyncMock, MagicMock
from bot.pipeline import TranscriptPipeline


@pytest.mark.asyncio
async def test_pipeline_emits_segment_with_speaker():
    async def fake_audio_stream():
        yield b"\x00" * 64000

    async def fake_transcribe(chunk):
        yield {"text": "Merhaba dünya", "language": "tr"}

    mock_bot = MagicMock()
    mock_bot.get_active_speaker = AsyncMock(return_value="Barbaros")

    mock_transcriber = MagicMock()
    mock_transcriber.transcribe_chunk = fake_transcribe

    mock_audio = MagicMock()
    mock_audio.stream = fake_audio_stream

    pipeline = TranscriptPipeline(bot=mock_bot, transcriber=mock_transcriber, audio=mock_audio)

    segments = []
    async for seg in pipeline.run(meeting_id="test001", max_chunks=1):
        segments.append(seg)

    assert len(segments) == 1
    assert segments[0]["speaker"] == "Barbaros"
    assert segments[0]["text"] == "Merhaba dünya"
    assert segments[0]["meeting_id"] == "test001"
    assert "timestamp" in segments[0]


@pytest.mark.asyncio
async def test_pipeline_uses_unknown_when_no_speaker():
    async def fake_audio_stream():
        yield b"\x00" * 64000

    async def fake_transcribe(chunk):
        yield {"text": "Test", "language": "en"}

    mock_bot = MagicMock()
    mock_bot.get_active_speaker = AsyncMock(return_value=None)

    mock_transcriber = MagicMock()
    mock_transcriber.transcribe_chunk = fake_transcribe

    mock_audio = MagicMock()
    mock_audio.stream = fake_audio_stream

    pipeline = TranscriptPipeline(bot=mock_bot, transcriber=mock_transcriber, audio=mock_audio)

    segments = []
    async for seg in pipeline.run(meeting_id="test002", max_chunks=1):
        segments.append(seg)

    assert segments[0]["speaker"] == "Unknown"


@pytest.mark.asyncio
async def test_pipeline_stops_at_max_chunks():
    call_count = 0

    async def fake_audio_stream():
        nonlocal call_count
        for _ in range(5):
            call_count += 1
            yield b"\x00" * 64000

    async def fake_transcribe(chunk):
        yield {"text": "test", "language": "en"}

    mock_bot = MagicMock()
    mock_bot.get_active_speaker = AsyncMock(return_value="Speaker")
    mock_transcriber = MagicMock()
    mock_transcriber.transcribe_chunk = fake_transcribe
    mock_audio = MagicMock()
    mock_audio.stream = fake_audio_stream

    pipeline = TranscriptPipeline(bot=mock_bot, transcriber=mock_transcriber, audio=mock_audio)

    segments = []
    async for seg in pipeline.run(meeting_id="test003", max_chunks=2):
        segments.append(seg)

    assert call_count == 2
