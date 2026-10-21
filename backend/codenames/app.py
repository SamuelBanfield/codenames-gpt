"""Load settings and assemble/own the running backend in one place."""

import asyncio
import logging

import websockets

from codenames.connections import Connections
from codenames.gpt.chat_gpt import ChatGPT
from codenames.options import Settings, load_settings
from codenames.rooms import Rooms
from codenames.websocket_server import WebSocketServer

logger = logging.getLogger(__name__)


async def serve(settings: Settings, rooms: Rooms):
    server = WebSocketServer(rooms)
    listener = None
    try:
        listener = await websockets.serve(server.handle_connection, settings.host, settings.websocket_port)
        logger.info("Server started on %s:%s", settings.host, settings.websocket_port)
        await asyncio.Future()
    finally:
        # Stop accepting/close sockets, then retire rooms before handler cleanup runs.
        if listener is not None:
            listener.close()
        try:
            await rooms.shutdown()
        finally:
            if listener is not None:
                await listener.wait_closed()


async def main():
    settings = load_settings()
    connections = Connections()

    def ai_factory():
        return ChatGPT(settings.openai_api_key, settings.gpt_model)

    rooms = Rooms(connections, ai_factory, settings.guess_delay)
    await serve(settings, rooms)
