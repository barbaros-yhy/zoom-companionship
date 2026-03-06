# bot/tests/test_ws_server.py
import pytest
import asyncio
import json
import websockets
from bot.ws_server import TranscriptWSServer


@pytest.mark.asyncio
async def test_ws_server_broadcasts_to_connected_client():
    server = TranscriptWSServer(port=8766)
    await server.start()

    received = []
    async with websockets.connect("ws://localhost:8766") as ws:
        await server.broadcast({
            "meeting_id": "abc123",
            "speaker": "Barbaros",
            "text": "Test mesaj",
            "timestamp": "00:01:00",
        })
        msg = await asyncio.wait_for(ws.recv(), timeout=2)
        received.append(json.loads(msg))

    await server.stop()

    assert len(received) == 1
    assert received[0]["speaker"] == "Barbaros"
    assert received[0]["text"] == "Test mesaj"


@pytest.mark.asyncio
async def test_ws_server_broadcast_with_no_clients():
    """Broadcast with no connected clients should not raise."""
    server = TranscriptWSServer(port=8767)
    await server.start()
    # Should not raise
    await server.broadcast({"text": "hello"})
    await server.stop()


@pytest.mark.asyncio
async def test_ws_server_stop_is_idempotent():
    """Calling stop() multiple times should not raise."""
    server = TranscriptWSServer(port=8768)
    await server.start()
    await server.stop()
    await server.stop()  # second call should be safe
