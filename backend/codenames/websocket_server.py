import asyncio
import json
import logging
import traceback
import websockets
from websockets import WebSocketServerProtocol
from typing import Any, Dict

from codenames.message_router.message_router import MessageRouter
from codenames.model import User, CodenamesConnection
from codenames.options import HOST, WEBSOCKET_PORT
from codenames.services.lobby_service import LobbyService, InMemoryLobbyRepository
from codenames.message_router.message_router import MessageRouter, UserContext
from codenames.services.connection_service import Connection, ConnectionManager

logger = logging.getLogger(__name__)

class WebSocketConnectionAdapter(CodenamesConnection):
    """Adapter to make WebSocketConnection compatible with CodenamesConnection"""
    
    def __init__(self, websocket_connection: 'WebSocketConnection'):
        super().__init__()
        self.websocket_connection = websocket_connection
        # Use the same UUID as the websocket connection
        self.uuid = websocket_connection.id
    
    async def send(self, message: Dict[str, Any]) -> None:
        await self.websocket_connection.send_message(message)

class WebSocketConnection(Connection):
    """WebSocket implementation of Connection"""
    
    def __init__(self, websocket: WebSocketServerProtocol):
        super().__init__()
        self.websocket = websocket
    
    async def send_message(self, message: Dict[str, Any]) -> None:
        try:
            await self.websocket.send(json.dumps(message))
            logger.debug(f"Sent message to {self.id}: {message.get('serverMessageType', 'unknown')}")
        except Exception as e:
            logger.error(f"Failed to send message to {self.id}: {e}")
            raise
    
    async def close(self) -> None:
        try:
            await self.websocket.close()
        except Exception as e:
            logger.debug(f"Error closing websocket {self.id}: {e}")

class WebSocketServer:
    """Main websocket server"""
    
    def __init__(self, lobby_service: LobbyService, connection_manager: ConnectionManager):
        self.lobby_service = lobby_service
        self.connection_manager = connection_manager
        self.message_router = MessageRouter(lobby_service)

    async def handle_connection(self, websocket: WebSocketServerProtocol, path: str) -> None:
        """Handle a new WebSocket connection"""
        connection = WebSocketConnection(websocket)
        connection_id = self.connection_manager.add_connection(connection)
        
        adapter = WebSocketConnectionAdapter(connection)
        user = User(adapter, True)
        user_context = UserContext(user, connection_id)
        
        logger.info(f"New connection established: {connection_id}")
        
        try:
            async for raw_message in websocket:
                await self._handle_message(user_context, raw_message)
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
        
        if message_type := message_data.get("clientMessageType"):
            if response := await self.message_router.route_message(user_context, message_type, message_data):
                if connection := self.connection_manager.get_connection(user_context.connection_id):
                    await connection.send_message(response)
        else:
            await self._send_error(user_context, "Missing clientMessageType")
    
    async def _send_error(self, user_context: UserContext, error_message: str) -> None:
        """Send an error message to the user"""
        connection = self.connection_manager.get_connection(user_context.connection_id)
        if connection:
            await connection.send_message({
                "serverMessageType": "error",
                "message": error_message
            })

    async def _cleanup_connection(self, user_context: UserContext) -> None:
        """Clean up when a connection is closed"""
        if user_context and user_context.lobby_id:
            await self.lobby_service.leave_lobby(user_context.user, user_context.lobby_id)

        self.connection_manager.remove_connection(user_context.connection_id)
        logger.info(f"Cleaned up connection {user_context.connection_id}")

async def create_server() -> WebSocketServer:
    """Factory function to create a properly configured server"""
    lobby_repository = InMemoryLobbyRepository()
    lobby_service = LobbyService(lobby_repository)
    connection_manager = ConnectionManager()
    
    return WebSocketServer(lobby_service, connection_manager)

async def main() -> None:
    """Main entry point"""
    server = await create_server()
    
    logger.info(f"Starting server on {HOST}:{WEBSOCKET_PORT}")
    async with websockets.serve(server.handle_connection, HOST, WEBSOCKET_PORT):
        logger.info(f"Server started on {HOST}:{WEBSOCKET_PORT}")
        await asyncio.Future()  # Run forever

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
