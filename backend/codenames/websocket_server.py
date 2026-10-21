import json
import logging
import traceback
import websockets
from websockets import WebSocketServerProtocol
from typing import Any, Dict

from codenames.model import User
from codenames.rooms import Rooms
from codenames.messages import MessageRouter
from codenames.connections import Connection, Session

logger = logging.getLogger(__name__)

class WebSocketConnection(Connection):
    """WebSocket implementation of Connection"""
    
    def __init__(self, websocket: WebSocketServerProtocol):
        self.websocket = websocket
    
    async def send(self, message: Dict[str, Any]) -> None:
        await self.websocket.send(json.dumps(message))
    
class WebSocketServer:
    """Main websocket server"""
    
    def __init__(self, rooms: Rooms):
        self.rooms = rooms
        self.connections = rooms.connections
        self.message_router = MessageRouter(rooms)

    async def handle_connection(self, websocket: WebSocketServerProtocol, path: str) -> None:
        """Handle a new WebSocket connection"""
        user = User()
        connection = WebSocketConnection(websocket)
        user_context = self.connections.add_session(user, connection)
        
        logger.info("New connection for player %s", user.id)
        
        try:
            async for raw_message in websocket:
                try:
                    await self._handle_message(user_context, raw_message)
                except Exception as e:
                    logger.error(f"Error for player {user.id} with message {raw_message}: {traceback.format_exc()}")
        except websockets.exceptions.ConnectionClosed:
            logger.info("Connection for player %s closed normally", user.id)
        except Exception as e:
            logger.error(f"Error for player {user.id}: {traceback.format_exc()}")
        finally:
            await self._cleanup_connection(user_context)
    
    async def _handle_message(self, user_context: Session, raw_message) -> None:
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
            logger.error(f"Invalid JSON from {user_context.user.id}: {e}")
            await self._send_error(user_context, "Invalid JSON format")
            return
        
        if not isinstance(message_data, dict):
            await self._send_error(user_context, "Message must be a JSON object")
            return
        message_type = message_data.get("clientMessageType")
        if isinstance(message_type, str) and message_type:
            logger.info(f"Received message from {user_context.user.id}: {message_data}")
            if response := await self.message_router.route_message(user_context, message_type, message_data):
                await self.connections.send(user_context.user.id, response)
        else:
            await self._send_error(user_context, "Missing clientMessageType")
    
    async def _send_error(self, user_context: Session, error_message: str) -> None:
        """Send an error message to the user"""
        await self.connections.send(user_context.user.id, {
            "serverMessageType": "error",
            "message": error_message,
        })

    async def _cleanup_connection(self, user_context: Session) -> None:
        """Clean up when a connection is closed"""
        try:
            if user_context.lobby_id:
                await self.rooms.leave_lobby(user_context.user, user_context.lobby_id)
        finally:
            self.connections.remove_session(user_context.user.id)
            logger.info("Cleaned up connection for player %s", user_context.user.id)
