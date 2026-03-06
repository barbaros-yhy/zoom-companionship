# bot/audio_capture.py
import asyncio
from typing import AsyncGenerator

SAMPLE_RATE = 16000
CHANNELS = 1
SAMPLE_WIDTH = 2  # 16-bit


class AudioCapture:
    """Captures audio from a PulseAudio monitor source as raw PCM chunks."""

    def __init__(self, chunk_ms: int = 2000, source_name: str = "virtual_sink.monitor"):
        self.chunk_ms = chunk_ms
        self.source_name = source_name
        bytes_per_ms = SAMPLE_RATE * CHANNELS * SAMPLE_WIDTH // 1000
        self.chunk_size_bytes = bytes_per_ms * chunk_ms
        self._process = None

    async def stream(self) -> AsyncGenerator[bytes, None]:
        """Stream raw PCM audio from PulseAudio monitor source."""
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
            data = await self._process.stdout.read(4096)
            if not data:
                break
            buffer.extend(data)
            while len(buffer) >= self.chunk_size_bytes:
                yield bytes(buffer[: self.chunk_size_bytes])
                buffer = buffer[self.chunk_size_bytes :]

    async def stop(self):
        if self._process:
            self._process.terminate()
            await self._process.wait()
            self._process = None
