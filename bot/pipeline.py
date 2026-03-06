# bot/pipeline.py
from datetime import datetime
from typing import AsyncGenerator


class TranscriptPipeline:
    """Orchestrates audio capture → STT → speaker tagging → segment emission."""

    def __init__(self, bot, transcriber, audio):
        self.bot = bot
        self.transcriber = transcriber
        self.audio = audio
        self._start_time: datetime | None = None

    def _elapsed_timestamp(self) -> str:
        if not self._start_time:
            return "00:00:00"
        elapsed = datetime.utcnow() - self._start_time
        total_seconds = int(elapsed.total_seconds())
        h, remainder = divmod(total_seconds, 3600)
        m, s = divmod(remainder, 60)
        return f"{h:02d}:{m:02d}:{s:02d}"

    async def run(
        self, meeting_id: str, max_chunks: int | None = None
    ) -> AsyncGenerator[dict, None]:
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
            if max_chunks is not None and chunks_processed >= max_chunks:
                break
