import asyncio
import json
from typing import override
import websockets

from codenames.model import CodenamesConnection, CodenamesGame

# import logging
# logging.basicConfig(level=logging.INFO)

HOST = "localhost"
PORT = 8765

GAME = CodenamesGame()

class CodenamesWebsocketConnection(CodenamesConnection):

    def __init__(self, socket):
        super().__init__()
        self.socket = socket

    @override
    async def send(self, message):
        await self.socket.send(message)

async def handle_websocket(websocket, path):
    print("New connection")
    # Handle incoming messages from the client
    connection = CodenamesWebsocketConnection(websocket)
    GAME.add_player(connection)
    print(len(GAME.players))
    GAME.start()

    async for message in websocket:
        # Process the message
        print(f"Received message: {message}")
        await GAME.request(connection, json.loads(message))

async def main():
    async with websockets.serve(handle_websocket, HOST, PORT):
        print(f"Server started on {HOST}:{PORT}")
        await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())