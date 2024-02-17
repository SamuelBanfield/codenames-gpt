import asyncio
import json
import pathlib
import traceback
from typing import override
import websockets

from codenames.lobby import Lobby
from codenames.model import CodenamesConnection, User

# import logging
# logging.basicConfig(level=logging.INFO)

properties_file_path = pathlib.Path(__file__).parent.parent / ".properties.json"

try:
    with open(properties_file_path) as property_file:
        properties = json.load(property_file)
except FileNotFoundError as e:
    raise FileNotFoundError(f"Could not find .properties.json file: {e}")

HOST = properties["host"]
PORT = properties["websocketPort"]

class CodenamesWebsocketConnection(CodenamesConnection):

    def __init__(self, socket):
        super().__init__()
        self.socket = socket

    @override
    async def send(self, message):
        # print(f"Sending message to client: {message}")
        await self.socket.send(message)

LOBBY = Lobby()

async def handle_websocket(websocket, path):
    print(f"New connection")
    connection = CodenamesWebsocketConnection(websocket)
    user = User(connection)
    LOBBY.add_user(user)
    print(f"There are now {len(LOBBY.users)} open connections")
    try:
        async for message in websocket:
            # Process the message
            json_message = json.loads(message)
            if "clientMessageType" in json_message and json_message["clientMessageType"] == "idRequest":
                # Silently send id to user
                to_send = json.dumps({"serverMessageType": "idAssign", "uuid": str(connection.uuid)})
                print(f"Sending message: {to_send}")
                await connection.send(to_send)
            else:
                print(f"Received message: {json_message}")
                await LOBBY.request(user, json_message)
    except Exception as e:
        if not isinstance(e, websockets.exceptions.ConnectionClosed):
            print(f"Encountered exception: {traceback.format_exc()}")
    finally:
        LOBBY.remove_user(user)
        print(f"Connection for user {user.connection.uuid} closed")

async def main():
    async with websockets.serve(handle_websocket, HOST, PORT):
        print(f"Server started on {HOST}:{PORT}")
        await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())