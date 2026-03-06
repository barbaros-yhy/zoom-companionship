# bot/transcriber.py
import httpx
from typing import AsyncGenerator

SAMPLE_RATE = 16000
CHANNELS = 1
SAMPLE_WIDTH = 2


class Transcriber:
    """Buffers audio chunks and sends them to Speaches for transcription."""

    def __init__(self, base_url: str = "http://localhost:8000", chunk_ms: int = 2000):
        self.base_url = base_url
        self.chunk_ms = chunk_ms
        bytes_per_ms = SAMPLE_RATE * CHANNELS * SAMPLE_WIDTH // 1000
        self.chunk_size_bytes = bytes_per_ms * chunk_ms
        self._buffer = bytearray()
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=30)
        return self._client

    async def transcribe_chunk(self, audio_bytes: bytes) -> AsyncGenerator[dict, None]:
        self._buffer.extend(audio_bytes)
        while len(self._buffer) >= self.chunk_size_bytes:
            chunk = bytes(self._buffer[: self.chunk_size_bytes])
            self._buffer = self._buffer[self.chunk_size_bytes :]
            segment = await self._send_to_speaches(chunk)
            if segment and segment.get("text", "").strip():
                yield segment

    async def _send_to_speaches(self, audio_bytes: bytes) -> dict:
        client = await self._get_client()
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

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()
