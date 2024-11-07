import asyncio
import json
import traceback
from uuid import UUID
import websockets
from websockets import WebSocketServerProtocol
from typing import Any, Dict

from codenames.lobby import Lobby
from codenames.model import CodenamesConnection, User
from codenames.options import HOST, WEBSOCKET_PORT

class CodenamesWebsocketConnection(CodenamesConnection):
    def __init__(self, socket: WebSocketServerProtocol):
        super().__init__()
        self.socket = socket

    async def send(self, message: Dict[str, Any]) -> None:
        await self.socket.send(json.dumps(message))

LOBBIES: Dict[UUID, Lobby] = {}

async def handle_message(user: User, message: str) -> None:
    json_message = json.loads(message)
    if json_message.get("clientMessageType") == "idRequest":
        to_send = {"serverMessageType": "idAssign", "uuid": str(user.connection.uuid)}
        print(f"Sending message: {to_send}")
        await user.connection.send(to_send)
        return
    for lobby in LOBBIES.values():
        if user in lobby.users:
            print(f"Received message: {json_message}")
            await lobby.request(user, json_message)
            return
    match json_message.get("clientMessageType"):
        case "createLobby":
            lobby_name = json_message.get("name")
            lobby = Lobby(user, lobby_name)
            LOBBIES[str(lobby.id)] = lobby
            to_send = {"serverMessageType": "lobbyJoined", "lobbyId": str(lobby.id)}
            print(f"Sending message: {to_send}")
            await user.connection.send(to_send)
        case "lobbiesRequest":
            to_send = {"serverMessageType": "lobbiesUpdate", "lobbies": [lobby.to_json() for lobby in LOBBIES.values()]}
            print(f"Sending message: {to_send}")
            await user.connection.send(to_send)
        case "joinLobby":
            lobby_id = json_message.get("lobbyId")
            if lobby_id in LOBBIES.keys():
                LOBBIES[lobby_id].add_user(user)
                to_send = {"serverMessageType": "lobbyJoined", "lobbyId": str(lobby_id)}
                print(f"Sending message: {to_send}")
                await user.connection.send(to_send)
            else:
                print(f"Request to join non-existent lobby: {lobby_id}")
        case _:
            print(f"Unhandled message: {json_message}")

async def handle_websocket(websocket: WebSocketServerProtocol, path: str) -> None:
    print("New connection")
    connection = CodenamesWebsocketConnection(websocket)
    user = User(connection, True)

    try:
        async for message in websocket:
            await handle_message(user, message)
    except websockets.exceptions.ConnectionClosed:
        pass
    except Exception as e:
        print(f"Encountered exception: {traceback.format_exc()}")
    finally:
        for lobby in LOBBIES.values():
            if user in lobby.users:
                lobby.remove_user(user)
                if not [user for user in lobby.users if user.is_human]:
                    LOBBIES.pop(str(lobby.id))
        print(f"Connection for user {user.connection.uuid} closed")

async def main() -> None:
    async with websockets.serve(handle_websocket, HOST, WEBSOCKET_PORT):
        print(f"Server started on {HOST}:{WEBSOCKET_PORT}")
        await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())