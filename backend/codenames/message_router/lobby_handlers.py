from typing import Dict, Any, Optional

from codenames.lobby import Lobby
from codenames.message_router.message_handler import UserContext
from codenames.services.lobby_service import LobbyService


class UpdatePreferencesHandler:
    """Handle user preferences update in lobby"""
    def __init__(self, lobby_service: LobbyService):
        self.lobby_service = lobby_service

    async def handle(self, user_context: UserContext, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if not user_context.lobby_id:
            return {
                "serverMessageType": "error",
                "message": "User not in a lobby"
            }
        lobby: Optional[Lobby] = await self.lobby_service.get_lobby(user_context.lobby_id)
        if not lobby:
            return {
                "serverMessageType": "error",
                "message": "Lobby not found"
            }
        lobby.update_user_preferences(user_context.user, data.get("player", {}))
        if lobby.all_ready():
            await lobby.start_game()
        else:
            await lobby.send_player_update()

