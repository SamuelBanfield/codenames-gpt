from typing import Dict, Any

from codenames.services.lobby_service import LobbyService
from codenames.message_router.message_handler import UserContext


class RequestIdHandler:
    """Handle ID assignment requests"""
    async def handle(self, user_context: UserContext, data: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "serverMessageType": "idAssign", 
            "uuid": user_context.connection_id
        }

class CreateLobbyHandler:
    """Handle lobby creation requests"""
    def __init__(self, lobby_service: LobbyService):
        self.lobby_service = lobby_service
    
    async def handle(self, user_context: UserContext, data: Dict[str, Any]) -> Dict[str, Any]:
        lobby_name = data.get("name", "Unnamed Lobby")
        if not isinstance(lobby_name, str) or not lobby_name.strip():
            raise ValueError("Lobby name must be a nonempty string")
        lobby = await self.lobby_service.create_lobby(user_context.user, lobby_name)
        user_context.join_lobby(str(lobby.id))
        
        return {
            "serverMessageType": "lobbyJoined", 
            "lobbyId": str(lobby.id)
        }

class JoinLobbyHandler:
    """Handle lobby join requests"""
    def __init__(self, lobby_service: LobbyService):
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
            if not user_context.user.in_lobby:
                user_context.leave_lobby()
            return {
                "serverMessageType": "error",
                "message": "Unable to join lobby"
            }

class RequestLobbiesHandler:
    """Handle request for available lobbies"""
    def __init__(self, lobby_service: LobbyService):
        self.lobby_service = lobby_service
    
    async def handle(self, user_context: UserContext, data: Dict[str, Any]) -> Dict[str, Any]:
        lobbies = await self.lobby_service.get_available_lobbies()
        return {
            "serverMessageType": "lobbiesUpdate", 
            "lobbies": [lobby.to_json() for lobby in lobbies]
        }


class LeaveLobbyHandler:
    def __init__(self, lobby_service: LobbyService):
        self.lobby_service = lobby_service

    async def handle(self, user_context: UserContext, data: Dict[str, Any]) -> Dict[str, Any]:
        if user_context.lobby_id:
            await self.lobby_service.leave_lobby(user_context.user, user_context.lobby_id)
        user_context.leave_lobby()
        return {"serverMessageType": "lobbyLeft"}
