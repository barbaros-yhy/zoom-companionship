# bot/caption_pipeline.py
"""
Caption-based transcript pipeline (alternative to audio capture).
"""
import asyncio
from datetime import datetime
from typing import AsyncGenerator


class CaptionPipeline:
    """
    Streams transcript segments from Zoom's native Live Captions.
    Replaces: AudioCapture → Transcriber → Speaker Tagging
    """

    def __init__(self, bot, caption_scraper):
        self.bot = bot
        self.caption_scraper = caption_scraper
        self._start_time: datetime | None = None
        self._queue = asyncio.Queue()
        self._running = False

    def _elapsed_timestamp(self) -> str:
        """Calculate elapsed time since meeting start."""
        if not self._start_time:
            return "00:00:00"
        elapsed = datetime.utcnow() - self._start_time
        total_seconds = int(elapsed.total_seconds())
        h, remainder = divmod(total_seconds, 3600)
        m, s = divmod(remainder, 60)
        return f"{h:02d}:{m:02d}:{s:02d}"

    async def _caption_callback(self, caption_data: dict):
        """Called by CaptionScraper when new caption arrives."""
        if not self._running:
            return

        # Add elapsed timestamp
        caption_data["elapsed_timestamp"] = self._elapsed_timestamp()

        # Put into queue for streaming
        await self._queue.put(caption_data)

    async def run(
        self, meeting_id: str, max_segments: int | None = None
    ) -> AsyncGenerator[dict, None]:
        """
        Stream transcript segments from Zoom captions.

        Yields:
            dict: {
                "meeting_id": str,
                "speaker": str,
                "text": str,
                "timestamp": str,
                "language": str
            }
        """
        self._start_time = datetime.utcnow()
        self._running = True
        segments_yielded = 0

        print("[caption_pipeline] Starting caption stream...")

        try:
            while self._running:
                # Wait for caption with timeout to allow checking _running flag
                try:
                    caption = await asyncio.wait_for(
                        self._queue.get(),
                        timeout=1.0  # Check running flag every second
                    )
                except asyncio.TimeoutError:
                    continue

                # Yield segment
                yield {
                    "meeting_id": meeting_id,
                    "speaker": caption.get("speaker", "Unknown"),
                    "text": caption.get("text", ""),
                    "timestamp": caption.get("elapsed_timestamp", "00:00:00"),
                    "language": "en",  # Zoom doesn't provide language in captions
                }

                segments_yielded += 1
                if max_segments is not None and segments_yielded >= max_segments:
                    print(f"[caption_pipeline] Reached max segments: {max_segments}")
                    break

        finally:
            self._running = False
            print("[caption_pipeline] Caption stream ended")

    def stop(self):
        """Stop the pipeline."""
        self._running = False
