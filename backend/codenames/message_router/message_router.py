from typing import Dict, Any, Optional
import logging

from codenames.message_router.game_handlers import GuessTileHandler, InitialiseGameHandler, ProvideClueHandler
from codenames.message_router.lobby_handlers import UpdatePreferencesHandler
from codenames.message_router.pre_lobby_handlers import CreateLobbyHandler, JoinLobbyHandler, RequestIdHandler, RequestLobbiesHandler
from codenames.message_router.message_handler import MessageHandler, UserContext

logger = logging.getLogger(__name__)


class MessageRouter:
    """Routes messages to appropriate handlers"""
    def __init__(self, lobby_service):
        self.handlers: Dict[str, MessageHandler] = {
            # Prelobby handlers
            "idRequest": RequestIdHandler(),
            "createLobby": CreateLobbyHandler(lobby_service),
            "joinLobby": JoinLobbyHandler(lobby_service),
            "lobbiesRequest": RequestLobbiesHandler(lobby_service),
            # Lobby handlers
            "preferencesRequest": UpdatePreferencesHandler(lobby_service),
            # Game handlers
            "initialiseRequest": InitialiseGameHandler(lobby_service),
            "guessTile": GuessTileHandler(lobby_service),
            "provideClue": ProvideClueHandler(lobby_service)
        }
    
    async def route_message(self, user_context: UserContext, message_type: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Route a message to the appropriate handler"""
        handler = self.handlers.get(message_type)
        if not handler:
            logger.warning(f"No handler for message type: {message_type}")
            return {"serverMessageType": "error", "message": f"Unknown message type: {message_type}"}
        
        try:
            return await handler.handle(user_context, data)
        except Exception as e:
            logger.error(f"Error handling message {message_type}: {e}")
            return {"serverMessageType": "error", "message": "Internal server error"}
