import asyncio
import json
import traceback
from uuid import UUID
from venv import logger
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

class MessageHandler:
    """Handles messages for a particular user and keeps track of their lobby"""
    def __init__(self, user: User):
        self.user = user
        self.lobby = None

    async def handle_message(self, message: str) -> None:
        json_message = json.loads(message)
        if self.lobby is not None:
            logger.info(f"Received message: {json_message}")
            await self.lobby.request(self.user, json_message)
            return
        match json_message.get("clientMessageType"):
            case "idRequest":
                await self.id_assign()
            case "createLobby":
                await self.create_lobby(json_message)
            case "lobbiesRequest":
                await self.lobbies_update()
            case "joinLobby":
                await self.join_lobby(json_message)
            case _:
                logger.warning(f"Unhandled message: {json_message}")

    async def send(self, to_send: Dict[str, Any]) -> None:
        logger.info(f"Sending message: {to_send}")
        await self.user.connection.send(to_send)

    async def id_assign(self) -> None:
        await self.send({"serverMessageType": "idAssign", "uuid": str(self.user.connection.uuid)})

    async def create_lobby(self, json_message: Dict[str, any]) -> None:
        lobby_name = json_message.get("name")
        lobby = Lobby(self.user, lobby_name)
        LOBBIES[str(lobby.id)] = lobby
        self.lobby = lobby
        await self.send({"serverMessageType": "lobbyJoined", "lobbyId": str(lobby.id)})

    async def lobbies_update(self) -> None:
        await self.send({"serverMessageType": "lobbiesUpdate", "lobbies": [lobby.to_json() for lobby in LOBBIES.values()]})

    async def join_lobby(self, json_message: Dict[str, any]) -> None:
        lobby_id = json_message.get("lobbyId")
        if lobby := LOBBIES.get(lobby_id):
            if lobby.game is not None or len(lobby.users) >= 4:
                logger.info(f"Request to join full lobby: {lobby_id}")
                return
            lobby.add_user(self.user)
            self.lobby = lobby
            await self.send({"serverMessageType": "lobbyJoined", "lobbyId": str(lobby_id)})
        else:
            logger.info(f"Request to join non-existent lobby: {lobby_id}")


async def handle_websocket(websocket: WebSocketServerProtocol, path: str) -> None:
    logger.info("New connection")
    user = User(CodenamesWebsocketConnection(websocket), True)
    message_handler = MessageHandler(user)

    try:
        async for message in websocket:
            await message_handler.handle_message(message)
    except websockets.exceptions.ConnectionClosed:
        pass
    except Exception as e:
        logger.error(f"Encountered exception: {traceback.format_exc()}")
    finally:
        if message_handler.lobby is not None:
            lobby = message_handler.lobby
            lobby.users.remove(user)
            if not [user for user in lobby.users if user.is_human]:
                LOBBIES.pop(str(lobby.id))
        logger.info(f"Connection for user {user.connection.uuid} closed")

async def main() -> None:
    async with websockets.serve(handle_websocket, HOST, WEBSOCKET_PORT):
        logger.info(f"Server started on {HOST}:{WEBSOCKET_PORT}")
        await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())