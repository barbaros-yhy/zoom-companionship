# bot/tests/test_transcriber.py
import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from bot.transcriber import Transcriber


@pytest.mark.asyncio
async def test_transcriber_buffers_small_chunks():
    """Small audio chunks should be buffered, not sent immediately."""
    transcriber = Transcriber(base_url="http://localhost:8000", chunk_ms=2000)
    tiny_chunk = b"\x00" * 100  # far less than 2s worth

    segments = []
    async for segment in transcriber.transcribe_chunk(tiny_chunk):
        segments.append(segment)

    assert segments == [], "Should not emit segments until buffer is full"


@pytest.mark.asyncio
async def test_transcriber_emits_segment_when_buffer_full():
    """When buffer reaches chunk_ms worth of audio, emit a transcript segment."""
    transcriber = Transcriber(base_url="http://localhost:8000", chunk_ms=2000)

    # 2000ms at 16kHz 16-bit mono = 64000 bytes
    full_chunk = b"\x00" * 64000

    mock_response = {"text": "merhaba dünya", "language": "tr"}

    with patch.object(transcriber, "_send_to_speaches", new_callable=AsyncMock, return_value=mock_response):
        segments = []
        async for segment in transcriber.transcribe_chunk(full_chunk):
            segments.append(segment)

    assert len(segments) == 1
    assert segments[0]["text"] == "merhaba dünya"
    assert segments[0]["language"] == "tr"


@pytest.mark.asyncio
async def test_transcriber_skips_empty_text():
    """Segments with empty or whitespace-only text should be dropped."""
    transcriber = Transcriber(base_url="http://localhost:8000", chunk_ms=2000)
    full_chunk = b"\x00" * 64000

    mock_response = {"text": "   ", "language": "tr"}

    with patch.object(transcriber, "_send_to_speaches", new_callable=AsyncMock, return_value=mock_response):
        segments = []
        async for segment in transcriber.transcribe_chunk(full_chunk):
            segments.append(segment)

    assert segments == [], "Whitespace-only text should be skipped"


@pytest.mark.asyncio
async def test_transcriber_chunk_size_bytes():
    """chunk_size_bytes should be correctly calculated from chunk_ms."""
    transcriber = Transcriber(base_url="http://localhost:8000", chunk_ms=2000)
    # 16000 samples/s * 2 bytes/sample * 2 seconds = 64000
    assert transcriber.chunk_size_bytes == 64000
