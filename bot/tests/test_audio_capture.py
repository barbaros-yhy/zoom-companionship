# bot/tests/test_audio_capture.py
from bot.audio_capture import AudioCapture


def test_chunk_size_bytes_100ms():
    capture = AudioCapture(chunk_ms=100)
    # 16000 Hz * 2 bytes * 0.1s = 3200 bytes
    assert capture.chunk_size_bytes == 3200


def test_chunk_size_bytes_2000ms():
    capture = AudioCapture(chunk_ms=2000)
    assert capture.chunk_size_bytes == 64000


def test_default_source_name():
    capture = AudioCapture()
    assert "monitor" in capture.source_name or capture.source_name == "default"


def test_default_chunk_ms():
    capture = AudioCapture()
    assert capture.chunk_ms == 2000
