# bot/transcriber.py
import io
import os
import wave
import httpx
from typing import AsyncGenerator

SAMPLE_RATE = 16000
CHANNELS = 1
SAMPLE_WIDTH = 2

DEFAULT_MODEL = os.getenv("WHISPER__MODEL", "Systran/faster-whisper-large-v3-turbo")


def _pcm_to_wav(pcm_bytes: bytes) -> bytes:
    """Wrap raw 16kHz mono 16-bit PCM bytes in a WAV container."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(SAMPLE_WIDTH)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(pcm_bytes)
    return buf.getvalue()


class Transcriber:
    """Buffers audio chunks and sends them to Speaches for transcription."""

    def __init__(self, base_url: str = "http://localhost:8000", chunk_ms: int = 2000,
                 model: str = DEFAULT_MODEL):
        self.base_url = base_url
        self.model = model
        self.chunk_ms = chunk_ms
        bytes_per_ms = SAMPLE_RATE * CHANNELS * SAMPLE_WIDTH // 1000
        self.chunk_size_bytes = bytes_per_ms * chunk_ms
        self._buffer = bytearray()
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            # CPU-only transcription is slow, need longer timeout
            self._client = httpx.AsyncClient(timeout=120)
        return self._client

    async def transcribe_chunk(self, audio_bytes: bytes) -> AsyncGenerator[dict, None]:
        self._buffer.extend(audio_bytes)
        while len(self._buffer) >= self.chunk_size_bytes:
            chunk = bytes(self._buffer[: self.chunk_size_bytes])
            self._buffer = self._buffer[self.chunk_size_bytes :]
            segment = await self._send_to_speaches(chunk)
            if segment and segment.get("text", "").strip():
                yield segment

    async def _send_to_speaches(self, pcm_bytes: bytes) -> dict:
        client = await self._get_client()
        wav_bytes = _pcm_to_wav(pcm_bytes)
        response = await client.post(
            f"{self.base_url}/v1/audio/transcriptions",
            files={"file": ("audio.wav", wav_bytes, "audio/wav")},
            data={
                "model": self.model,
                "response_format": "json",
            },
        )
        response.raise_for_status()
        return response.json()

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()
