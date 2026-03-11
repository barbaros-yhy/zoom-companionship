# bot/main.py
"""
Zoom Companion Bot — Entry Point

Scrapes Zoom's native Live Transcript (Closed Captions) and generates AI summaries.

Usage:
  python -m bot.main --meeting-url "https://zoom.us/j/123" --meeting-id "abc12345"
  python -m bot.main --meeting-url "https://zoom.us/j/123" --meeting-id "abc12345" --no-summary

Requirements:
  - Host must enable "Closed Caption" in the meeting
  - Bot can request captions (host must approve within 60s)
"""
import asyncio
import argparse
import os
import sys
from dotenv import load_dotenv

load_dotenv()


def _require_env(key: str) -> str:
    val = os.getenv(key, "").strip()
    if not val:
        print(f"[bot] ERROR: {key} environment variable is required", file=sys.stderr)
        sys.exit(1)
    return val


from bot.playwright_bot import ZoomBot
from bot.caption_scraper import CaptionScraper
from bot.caption_pipeline import CaptionPipeline
from bot.ws_server import TranscriptWSServer
from bot.storage import Storage


async def run_meeting(meeting_url: str, meeting_id: str, skip_summary: bool = False):
    """
    Run the bot with caption scraping mode.

    Args:
        meeting_url: Zoom meeting URL
        meeting_id: Unique meeting identifier
        skip_summary: Skip AI summary generation
    """
    storage = Storage(
        db_path=os.getenv("DB_PATH", "/data/meetings.db"),
        local_dir=os.getenv("TRANSCRIPT_DIR", "/data/transcripts"),
    )
    ws_server = TranscriptWSServer(port=int(os.getenv("BOT_WS_PORT", "8765")))
    bot = ZoomBot(display_name=os.getenv("BOT_NAME", "Companion"))

    print("[bot] 🎯 Using CAPTION MODE (Zoom Live Transcript)")

    await ws_server.start()
    print(f"[bot] WS server started on port {os.getenv('BOT_WS_PORT', '8765')}")

    await bot.join(meeting_url)
    print(f"[bot] ✓ Joined: {meeting_url}")

    # Initialize caption scraper after bot has joined
    caption_pipeline = CaptionPipeline(bot=bot, caption_scraper=None)

    caption_scraper = CaptionScraper(
        page=bot._page,
        on_caption=caption_pipeline._caption_callback
    )

    # Enable captions and inject scraper
    success = await caption_scraper.enable_captions()
    if not success:
        print("[bot] ✗ FATAL: Could not enable Zoom captions")
        print("[bot] Make sure:")
        print("  1. Host has enabled 'Closed Caption' in meeting")
        print("  2. Or request captions and wait for host approval")
        await bot.leave()
        await ws_server.stop()
        sys.exit(1)

    caption_pipeline.caption_scraper = caption_scraper

    await bot.send_chat_message("Live transcript scraping started ✅")
    print("[bot] ✓ Caption scraper active, streaming transcripts...")

    # Main transcript loop
    participants: set[str] = set()
    try:
        async for segment in caption_pipeline.run(meeting_id=meeting_id):
            if segment["speaker"] != "Unknown":
                participants.add(segment["speaker"])
            storage.append_segment(
                meeting_id=meeting_id,
                speaker=segment["speaker"],
                text=segment["text"],
                timestamp=segment["timestamp"],
            )
            await ws_server.broadcast(segment)
            print(f"[{segment['timestamp']}] {segment['speaker']}: {segment['text']}")
    except KeyboardInterrupt:
        print("\n[bot] Interrupted by user, cleaning up...")
    except Exception as e:
        print(f"[bot] Error in transcript loop: {e}")
        import traceback
        traceback.print_exc()

    # Summary generation
    if skip_summary:
        print("[bot] Skipping summary (--no-summary mode).")
        storage.complete_meeting(
            meeting_id=meeting_id,
            summary="",
            action_items=[],
            participants=list(participants),
        )
    else:
        from bot.summarizer import Summarizer
        summarizer = Summarizer(region=os.getenv("AWS_REGION", "eu-central-1"))
        print("[bot] Meeting ended, generating summary...")
        segments = storage.get_segments(meeting_id)
        transcript_text = "\n".join(
            f"[{s['timestamp']}] **{s['speaker']}:** {s['text']}" for s in segments
        )
        result = await summarizer.generate_async(
            transcript=transcript_text,
            participants=list(participants),
        )
        storage.complete_meeting(
            meeting_id=meeting_id,
            summary="\n".join(result["summary"]),
            action_items=result["action_items"],
            participants=list(participants),
        )
        print("[bot] Summary saved.")

    # Cleanup
    await caption_scraper.disable()
    await bot.leave()
    await ws_server.stop()


def main():
    parser = argparse.ArgumentParser(description="Zoom Companion Bot - Live Transcript Scraper")
    parser.add_argument("--meeting-url", required=True, help="Zoom meeting URL")
    parser.add_argument("--meeting-id", required=True, help="Unique meeting identifier")
    parser.add_argument("--no-summary", action="store_true", help="Skip AI summary generation")
    args = parser.parse_args()
    asyncio.run(
        run_meeting(
            args.meeting_url,
            args.meeting_id,
            skip_summary=args.no_summary
        )
    )


if __name__ == "__main__":
    main()
