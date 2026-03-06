# bot/transcriber.py
import httpx
from typing import AsyncGenerator

# Audio constants: 16kHz, 16-bit mono (Speaches/Whisper standard)
SAMPLE_RATE = 16000
CHANNELS = 1
SAMPLE_WIDTH = 2  # bytes (16-bit)


class Transcriber:
    """Buffers audio chunks and sends them to Speaches for transcription."""

    def __init__(self, base_url: str = "http://localhost:8000", chunk_ms: int = 2000):
        self.base_url = base_url
        self.chunk_ms = chunk_ms
        # bytes per ms at 16kHz 16-bit mono
        bytes_per_ms = SAMPLE_RATE * CHANNELS * SAMPLE_WIDTH // 1000
        self.chunk_size_bytes = bytes_per_ms * chunk_ms
        self._buffer = bytearray()

    async def transcribe_chunk(self, audio_bytes: bytes) -> AsyncGenerator[dict, None]:
        """Buffer audio and yield transcript segments when buffer is full."""
        self._buffer.extend(audio_bytes)

        while len(self._buffer) >= self.chunk_size_bytes:
            chunk = bytes(self._buffer[: self.chunk_size_bytes])
            self._buffer = self._buffer[self.chunk_size_bytes :]

            segment = await self._send_to_speaches(chunk)
            if segment and segment.get("text", "").strip():
                yield segment

    async def _send_to_speaches(self, audio_bytes: bytes) -> dict:
        """POST raw PCM audio to Speaches and return transcript dict."""
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                f"{self.base_url}/v1/audio/transcriptions",
                files={"file": ("audio.raw", audio_bytes, "audio/octet-stream")},
                data={
                    "model": "Systran/faster-whisper-large-v3-turbo",
                    "response_format": "json",
                },
            )
            response.raise_for_status()
            return response.json()
