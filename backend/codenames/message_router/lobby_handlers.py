from asyncio.log import logger
from typing import Dict, Any, Optional

from codenames.model import Role, User
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
        user: User = user_context.user
        player_data = data.get("player", {})
        
        user.name = player_data.get("name", user.name) or user.name
        user.is_ready = player_data.get("ready", user.is_ready) or user.is_ready
        if "role" in player_data and player_data["role"] is not None:
            index = int(player_data["role"])
            assigned_roles = lobby.get_role_assignments()
            if index not in assigned_roles:
                role = Role.from_index(index)
                user.team, user.is_spy_master = role.team, role.is_spymaster

        if all(user.is_ready for user in lobby.users if user.name):
            logger.info("Starting game...")
            await lobby.start_game()
        else:
            await lobby.send_player_update()
            

