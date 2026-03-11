# bot/main.py
"""
Zoom Companion Bot — Entry Point

Usage:
  # Audio mode (default - uses Whisper transcription)
  python -m bot.main --meeting-url "https://zoom.us/j/123" --meeting-id "abc12345"

  # Caption mode (uses Zoom's native Live Transcript)
  python -m bot.main --meeting-url "https://zoom.us/j/123" --meeting-id "abc12345" --use-captions
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
from bot.ws_server import TranscriptWSServer
from bot.storage import Storage


async def run_meeting(meeting_url: str, meeting_id: str, skip_summary: bool = False, use_captions: bool = False):
    """
    Run the bot with either audio capture or caption scraping mode.

    Args:
        meeting_url: Zoom meeting URL
        meeting_id: Unique meeting identifier
        skip_summary: Skip AI summary generation
        use_captions: Use Zoom's Live Transcript instead of audio capture
    """
    storage = Storage(
        db_path=os.getenv("DB_PATH", "/data/meetings.db"),
        local_dir=os.getenv("TRANSCRIPT_DIR", "/data/transcripts"),
    )
    ws_server = TranscriptWSServer(port=int(os.getenv("BOT_WS_PORT", "8765")))
    bot = ZoomBot(display_name=os.getenv("BOT_NAME", "Companion"))

    # Choose pipeline based on mode
    if use_captions:
        print("[bot] 🎯 Using CAPTION MODE (Zoom Live Transcript)")
        from bot.caption_scraper import CaptionScraper
        from bot.caption_pipeline import CaptionPipeline

        # Caption scraper needs the page, so we initialize it after bot.join()
        caption_scraper = None
        pipeline = None
    else:
        print("[bot] 🎤 Using AUDIO MODE (Whisper transcription)")
        from bot.audio_capture import AudioCapture
        from bot.transcriber import Transcriber
        from bot.pipeline import TranscriptPipeline

        audio = AudioCapture()
        transcriber = Transcriber(base_url=os.getenv("SPEACHES_URL", "http://localhost:8000"))
        pipeline = TranscriptPipeline(bot=bot, transcriber=transcriber, audio=audio)

    await ws_server.start()
    print(f"[bot] WS server started on port {os.getenv('BOT_WS_PORT', '8765')}")

    await bot.join(meeting_url)
    print(f"[bot] ✓ Joined: {meeting_url}")

    # Caption mode: Initialize caption scraper after bot has joined
    if use_captions:
        from bot.caption_scraper import CaptionScraper
        from bot.caption_pipeline import CaptionPipeline

        # Create caption scraper with callback
        caption_pipeline = CaptionPipeline(bot=bot, caption_scraper=None)  # Will inject scraper next

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
        pipeline = caption_pipeline

        await bot.send_chat_message("Live transcript scraping started \u2705")
        print("[bot] ✓ Caption scraper active, streaming transcripts...")

    else:
        # Audio mode: Send chat message
        await bot.send_chat_message("Audio transcription started \u2705")
        print("[bot] ✓ Audio pipeline active, streaming transcripts...")

    # Main transcript loop (same for both modes)
    participants: set[str] = set()
    try:
        async for segment in pipeline.run(meeting_id=meeting_id):
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

    # Summary generation (same for both modes)
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

    # Cleanup (mode-dependent)
    if use_captions:
        await caption_scraper.disable()
    else:
        await transcriber.close()

    await bot.leave()
    await ws_server.stop()


def main():
    parser = argparse.ArgumentParser(description="Zoom Companion Bot")
    parser.add_argument("--meeting-url", required=True, help="Zoom meeting URL")
    parser.add_argument("--meeting-id", required=True, help="Unique meeting identifier")
    parser.add_argument("--no-summary", action="store_true", help="Skip AI summary generation")
    parser.add_argument(
        "--use-captions",
        action="store_true",
        help="Use Zoom Live Transcript (DOM scraping) instead of audio capture"
    )
    args = parser.parse_args()
    asyncio.run(
        run_meeting(
            args.meeting_url,
            args.meeting_id,
            skip_summary=args.no_summary,
            use_captions=args.use_captions
        )
    )


if __name__ == "__main__":
    main()
