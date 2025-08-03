from typing import Dict, Any, Protocol, Optional
import logging

logger = logging.getLogger(__name__)

class MessageHandler(Protocol):
    """Protocol for handling different message types"""
    async def handle(self, user_context: 'UserContext', data: Dict[str, Any]) -> Dict[str, Any]:
        ...

class UserContext:
    """Context for a user session"""
    def __init__(self, user, connection_id: str):
        self.user = user
        self.connection_id = connection_id
        self.lobby_id: Optional[str] = None
    
    def join_lobby(self, lobby_id: str) -> None:
        self.lobby_id = lobby_id
    
    def leave_lobby(self) -> None:
        self.lobby_id = None

class IdRequestHandler:
    """Handle ID assignment requests"""
    async def handle(self, user_context: UserContext, data: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "serverMessageType": "idAssign", 
            "uuid": user_context.connection_id
        }

class CreateLobbyHandler:
    """Handle lobby creation requests"""
    def __init__(self, lobby_service):
        self.lobby_service = lobby_service
    
    async def handle(self, user_context: UserContext, data: Dict[str, Any]) -> Dict[str, Any]:
        lobby_name = data.get("name", "Unnamed Lobby")
        lobby = await self.lobby_service.create_lobby(user_context.user, lobby_name)
        user_context.join_lobby(str(lobby.id))
        
        return {
            "serverMessageType": "lobbyJoined", 
            "lobbyId": str(lobby.id)
        }

class JoinLobbyHandler:
    """Handle lobby join requests"""
    def __init__(self, lobby_service):
        self.lobby_service = lobby_service
    
    async def handle(self, user_context: UserContext, data: Dict[str, Any]) -> Dict[str, Any]:
        lobby_id = data.get("lobbyId")
        if not lobby_id:
            raise ValueError("Missing lobbyId in join request")
        
        lobby = await self.lobby_service.join_lobby(user_context.user, lobby_id)
        if lobby:
            user_context.join_lobby(lobby_id)
            return {
                "serverMessageType": "lobbyJoined", 
                "lobbyId": lobby_id
            }
        else:
            return {
                "serverMessageType": "error",
                "message": "Unable to join lobby"
            }

class LobbiesRequestHandler:
    """Handle request for available lobbies"""
    def __init__(self, lobby_service):
        self.lobby_service = lobby_service
    
    async def handle(self, user_context: UserContext, data: Dict[str, Any]) -> Dict[str, Any]:
        lobbies = await self.lobby_service.get_available_lobbies()
        return {
            "serverMessageType": "lobbiesUpdate", 
            "lobbies": [lobby.to_json() for lobby in lobbies]
        }

class MessageRouter:
    """Routes messages to appropriate handlers"""
    def __init__(self, lobby_service):
        self.handlers = {
            "idRequest": IdRequestHandler(),
            "createLobby": CreateLobbyHandler(lobby_service),
            "joinLobby": JoinLobbyHandler(lobby_service),
            "lobbiesRequest": LobbiesRequestHandler(lobby_service),
        }
    
    async def route_message(self, user_context: UserContext, message_type: str, data: Dict[str, Any]) -> Dict[str, Any]:
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
