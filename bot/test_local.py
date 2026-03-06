"""
Local test script — Speaches + Storage + WebSocket pipeline'ını test eder.
Zoom'a katılmaz, PulseAudio gerektirmez.

Kullanım:
  python bot/test_local.py --audio path/to/test.wav
  python bot/test_local.py --demo   # sessiz audio ile sadece pipeline testi

Gereksinimler:
  docker compose up speaches -d   (CPU mode için aşağıya bak)
"""
import asyncio
import argparse
import os
import tempfile
import struct
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()


def _make_silent_wav(duration_sec: int = 5, path: str = None) -> str:
    """16kHz mono 16-bit sessiz WAV dosyası oluşturur."""
    if path is None:
        path = tempfile.mktemp(suffix=".wav")
    sample_rate = 16000
    num_samples = sample_rate * duration_sec
    with open(path, "wb") as f:
        # WAV header
        data_size = num_samples * 2
        f.write(b"RIFF")
        f.write(struct.pack("<I", 36 + data_size))
        f.write(b"WAVE")
        f.write(b"fmt ")
        f.write(struct.pack("<IHHIIHH", 16, 1, 1, sample_rate, sample_rate * 2, 2, 16))
        f.write(b"data")
        f.write(struct.pack("<I", data_size))
        f.write(b"\x00" * data_size)
    return path


async def _fake_audio_stream(wav_path: str, chunk_ms: int = 2000):
    """WAV dosyasını chunk'lara bölerek stream eder (PulseAudio yerine)."""
    sample_rate = 16000
    bytes_per_ms = sample_rate * 2 // 1000
    chunk_size = bytes_per_ms * chunk_ms

    with open(wav_path, "rb") as f:
        # WAV header'ı atla (44 byte)
        f.seek(44)
        while True:
            data = f.read(chunk_size)
            if not data:
                break
            # chunk_size'dan kısa ise padding ekle
            if len(data) < chunk_size:
                data = data + b"\x00" * (chunk_size - len(data))
            yield data
            await asyncio.sleep(chunk_ms / 1000)  # gerçek zamanlı simüle et


async def run_local_test(audio_path: str):
    from bot.transcriber import Transcriber
    from bot.storage import Storage
    from bot.ws_server import TranscriptWSServer

    speaches_url = os.getenv("SPEACHES_URL", "http://localhost:8000")
    ws_port = int(os.getenv("BOT_WS_PORT", "8765"))

    # Storage — temp dizinde
    tmp_dir = tempfile.mkdtemp()
    meeting_id = "local-test-001"
    storage = Storage(
        db_path=os.path.join(tmp_dir, "test.db"),
        local_dir=tmp_dir,
    )
    storage.create_meeting("Local Test", "zoom", "https://zoom.us/j/test")

    # WebSocket server
    ws_server = TranscriptWSServer(port=ws_port)
    await ws_server.start()
    print(f"[test] WS server başladı: ws://localhost:{ws_port}")
    print(f"[test] Dashboard'u aç: http://localhost:3000")
    print(f"[test] Speaches: {speaches_url}")
    print(f"[test] Audio: {audio_path}")
    print("─" * 50)

    # Transcriber
    transcriber = Transcriber(base_url=speaches_url, chunk_ms=2000)

    chunk_count = 0
    speaker_names = ["Barbaros", "Ahmet", "Elif"]  # fake speaker rotation

    async for audio_chunk in _fake_audio_stream(audio_path):
        chunk_count += 1
        # Fake speaker (gerçek testte Zoom'dan gelir)
        speaker = speaker_names[(chunk_count - 1) % len(speaker_names)]

        async for segment in transcriber.transcribe_chunk(audio_chunk):
            print(f"[{chunk_count:03d}] {speaker}: {segment['text']}")
            storage.append_segment(
                meeting_id=meeting_id,
                speaker=speaker,
                text=segment["text"],
                timestamp=f"00:{chunk_count // 30:02d}:{(chunk_count % 30) * 2:02d}",
            )
            await ws_server.broadcast({
                "meeting_id": meeting_id,
                "speaker": speaker,
                "text": segment["text"],
                "timestamp": f"00:{chunk_count // 30:02d}:{(chunk_count % 30) * 2:02d}",
            })

    transcript_path = Path(tmp_dir) / f"{meeting_id}_transcript.md"
    print("─" * 50)
    print(f"[test] Tamamlandı. Transcript: {transcript_path}")
    if transcript_path.exists():
        print(transcript_path.read_text())

    await transcriber.close()
    await ws_server.stop()


def main():
    parser = argparse.ArgumentParser(description="Local pipeline test (no Zoom, no PulseAudio)")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--audio", help="Test WAV dosyası (16kHz mono)")
    group.add_argument("--demo", action="store_true", help="Sessiz audio ile demo")
    args = parser.parse_args()

    if args.demo:
        print("[test] Demo mode: 10 saniyelik sessiz audio oluşturuluyor...")
        audio_path = _make_silent_wav(duration_sec=10)
        print(f"[test] Oluşturuldu: {audio_path}")
    else:
        audio_path = args.audio

    asyncio.run(run_local_test(audio_path))


if __name__ == "__main__":
    main()
