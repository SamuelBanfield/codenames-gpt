import asyncio
import json
import logging
import traceback
import websockets
from websockets import WebSocketServerProtocol
from typing import Any, Dict

from codenames.model import User
from codenames.options import HOST, WEBSOCKET_PORT
from codenames.services.lobby_service import LobbyService, InMemoryLobbyRepository
from codenames.message_router.message_router import MessageRouter, UserContext
from codenames.services.connection_service import Connection, ConnectionManager

logger = logging.getLogger(__name__)

class WebSocketConnection(Connection):
    """WebSocket implementation of Connection"""
    
    def __init__(self, websocket: WebSocketServerProtocol, connection_id: str):
        super().__init__(connection_id)
        self.websocket = websocket
    
    async def send(self, message: Dict[str, Any]) -> None:
        try:
            await self.websocket.send(json.dumps(message))
            logger.debug(f"Sent message to {self.id}: {message.get('serverMessageType', 'unknown')}")
        except Exception as e:
            logger.error(f"Failed to send message to {self.id}: {e}")
            raise
    
class WebSocketServer:
    """Main websocket server"""
    
    def __init__(self, lobby_service: LobbyService):
        self.lobby_service = lobby_service
        self.connection_manager = lobby_service.connections
        self.message_router = MessageRouter(lobby_service)

    async def handle_connection(self, websocket: WebSocketServerProtocol, path: str) -> None:
        """Handle a new WebSocket connection"""
        user = User()
        connection = WebSocketConnection(websocket, user.id)
        user_context = self.connection_manager.add_session(user, connection)
        connection_id = connection.id
        
        logger.info(f"New connection established: {connection_id}")
        
        try:
            async for raw_message in websocket:
                try:
                    await self._handle_message(user_context, raw_message)
                except Exception as e:
                    logger.error(f"Error in connection {connection_id} with message {raw_message}: {traceback.format_exc()}")
        except websockets.exceptions.ConnectionClosed:
            logger.info(f"Connection {connection_id} closed normally")
        except Exception as e:
            logger.error(f"Error in connection {connection_id}: {traceback.format_exc()}")
        finally:
            await self._cleanup_connection(user_context)
    
    async def _handle_message(self, user_context: UserContext, raw_message) -> None:
        """Handle an incoming message"""
        if isinstance(raw_message, str):
            message_str = raw_message
        elif isinstance(raw_message, bytes):
            message_str = raw_message.decode('utf-8')
        else:
            message_str = str(raw_message)

        try:
            message_data = json.loads(message_str)
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON from {user_context.connection_id}: {e}")
            await self._send_error(user_context, "Invalid JSON format")
            return
        
        if not isinstance(message_data, dict):
            await self._send_error(user_context, "Message must be a JSON object")
            return
        message_type = message_data.get("clientMessageType")
        if isinstance(message_type, str) and message_type:
            logger.info(f"Received message from {user_context.connection_id}: {message_data}")
            if response := await self.message_router.route_message(user_context, message_type, message_data):
                await self.connection_manager.send(user_context.user.id, response)
        else:
            await self._send_error(user_context, "Missing clientMessageType")
    
    async def _send_error(self, user_context: UserContext, error_message: str) -> None:
        """Send an error message to the user"""
        await self.connection_manager.send(user_context.user.id, {
            "serverMessageType": "error",
            "message": error_message,
        })

    async def _cleanup_connection(self, user_context: UserContext) -> None:
        """Clean up when a connection is closed"""
        try:
            if user_context.lobby_id:
                await self.lobby_service.leave_lobby(user_context.user, user_context.lobby_id)
        finally:
            self.connection_manager.remove_session(user_context.user.id)
            logger.info(f"Cleaned up connection {user_context.connection_id}")

async def create_server() -> WebSocketServer:
    """Factory function to create a properly configured server"""
    lobby_repository = InMemoryLobbyRepository()
    connection_manager = ConnectionManager()
    lobby_service = LobbyService(lobby_repository, connection_manager)
    
    return WebSocketServer(lobby_service)

async def main() -> None:
    """Main entry point"""
    server = await create_server()
    
    logger.info(f"Starting server on {HOST}:{WEBSOCKET_PORT}")
    async with websockets.serve(server.handle_connection, HOST, WEBSOCKET_PORT):
        logger.info(f"Server started on {HOST}:{WEBSOCKET_PORT}")
        try:
            await asyncio.Future()  # Run forever
        finally:
            for lobby in await server.lobby_service.repository.list_lobbies():
                if lobby.game:
                    await lobby.game.dispose()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
