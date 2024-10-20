import asyncio
import json
import traceback
import websockets

from codenames.lobby import Lobby
from codenames.model import CodenamesConnection, User
from codenames.options import HOST, WEBSOCKET_PORT

class CodenamesWebsocketConnection(CodenamesConnection):

    def __init__(self, socket):
        super().__init__()
        self.socket = socket

    async def send(self, message):
        await self.socket.send(json.dumps(message))

LOBBY = Lobby()

async def handle_websocket(websocket, path):
    print(f"New connection")
    connection = CodenamesWebsocketConnection(websocket)
    user = User(connection)
    LOBBY.add_user(user)
    print(f"There are now {len(LOBBY.users)} open connections")
    try:
        async for message in websocket:
            json_message = json.loads(message)
            if "clientMessageType" in json_message and json_message["clientMessageType"] == "idRequest":
                to_send = {"serverMessageType": "idAssign", "uuid": str(connection.uuid)}
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
    async with websockets.serve(handle_websocket, HOST, WEBSOCKET_PORT):
        print(f"Server started on {HOST}:{WEBSOCKET_PORT}")
        await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())