# bot/ws_server.py
import asyncio
import json
import websockets
from websockets.server import WebSocketServerProtocol


class TranscriptWSServer:
    """WebSocket server that broadcasts transcript segments to dashboard clients."""

    def __init__(self, port: int = 8765):
        self.port = port
        self._clients: set[WebSocketServerProtocol] = set()
        self._server = None

    async def _handler(self, websocket: WebSocketServerProtocol):
        self._clients.add(websocket)
        try:
            await websocket.wait_closed()
        finally:
            self._clients.discard(websocket)

    async def start(self):
        self._server = await websockets.serve(self._handler, "0.0.0.0", self.port)

    async def stop(self):
        if self._server:
            self._server.close()
            await self._server.wait_closed()
            self._server = None

    async def broadcast(self, segment: dict):
        if not self._clients:
            return
        message = json.dumps(segment)
        await asyncio.gather(
            *[client.send(message) for client in self._clients],
            return_exceptions=True,
        )
