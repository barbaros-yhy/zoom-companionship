# bot/main.py
"""
Zoom Companion Bot — Entry Point

Usage:
  python -m bot.main --meeting-url "https://zoom.us/j/123" --meeting-id "abc12345"
"""
import asyncio
import argparse
import os
from dotenv import load_dotenv

load_dotenv()

from bot.playwright_bot import ZoomBot
from bot.audio_capture import AudioCapture
from bot.transcriber import Transcriber
from bot.pipeline import TranscriptPipeline
from bot.ws_server import TranscriptWSServer
from bot.storage import Storage
from bot.summarizer import Summarizer


async def run_meeting(meeting_url: str, meeting_id: str):
    storage = Storage(
        db_path=os.getenv("DB_PATH", "/data/meetings.db"),
        local_dir=os.getenv("TRANSCRIPT_DIR", "/data/transcripts"),
    )
    ws_server = TranscriptWSServer(port=int(os.getenv("BOT_WS_PORT", "8765")))
    bot = ZoomBot(display_name=os.getenv("BOT_NAME", "Companion"))
    audio = AudioCapture()
    transcriber = Transcriber(base_url=os.getenv("SPEACHES_URL", "http://localhost:8000"))
    pipeline = TranscriptPipeline(bot=bot, transcriber=transcriber, audio=audio)
    summarizer = Summarizer(api_key=os.getenv("ANTHROPIC_API_KEY", ""))

    await ws_server.start()
    print(f"[bot] WS server started on port {os.getenv('BOT_WS_PORT', '8765')}")

    await bot.join(meeting_url)
    await bot.send_chat_message("Transcription started \u2705")
    print(f"[bot] Joined: {meeting_url}")

    participants: set[str] = set()
    async for segment in pipeline.run(meeting_id=meeting_id):
        participants.add(segment["speaker"])
        storage.append_segment(
            meeting_id=meeting_id,
            speaker=segment["speaker"],
            text=segment["text"],
            timestamp=segment["timestamp"],
        )
        await ws_server.broadcast(segment)
        print(f"[{segment['timestamp']}] {segment['speaker']}: {segment['text']}")

    print("[bot] Meeting ended, generating summary...")
    segments = storage.get_segments(meeting_id)
    transcript_text = "\n".join(
        f"[{s['timestamp']}] **{s['speaker']}:** {s['text']}" for s in segments
    )
    result = summarizer.generate(
        transcript=transcript_text,
        participants=list(participants),
    )
    storage.complete_meeting(
        meeting_id=meeting_id,
        summary="\n".join(result["summary"]),
        action_items=result["action_items"],
    )
    print("[bot] Summary saved.")

    await bot.leave()
    await ws_server.stop()


def main():
    parser = argparse.ArgumentParser(description="Zoom Companion Bot")
    parser.add_argument("--meeting-url", required=True, help="Zoom meeting URL")
    parser.add_argument("--meeting-id", required=True, help="Meeting ID from the API")
    args = parser.parse_args()
    asyncio.run(run_meeting(args.meeting_url, args.meeting_id))


if __name__ == "__main__":
    main()
