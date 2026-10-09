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
                "serverMessageType": "stateError",
                "message": "User not in a lobby"
            }
        lobby: Optional[Lobby] = await self.lobby_service.get_lobby(user_context.lobby_id)
        if not lobby:
            return {
                "serverMessageType": "stateError",
                "message": "Lobby not found"
            }
        user: User = user_context.user
        if user not in lobby.users:
            return {"serverMessageType": "stateError", "message": "User not in this lobby"}
        player_data = data.get("player", {})
        if not isinstance(player_data, dict):
            raise ValueError("Player preferences must be an object")
        if lobby.game:
            if player_data:
                return {"serverMessageType": "error", "message": "Preferences cannot change after game startup"}
            await lobby.send_player_update()
            return
        if "name" in player_data and (not isinstance(player_data["name"], str) or not player_data["name"].strip()):
            raise ValueError("Name must be a nonempty string")
        if "ready" in player_data and type(player_data["ready"]) is not bool:
            raise ValueError("Ready must be a boolean")
        role = None
        if "role" in player_data and player_data["role"] is not None:
            index = player_data["role"]
            if type(index) is not int:
                raise ValueError("Role must be an integer")
            role = Role.from_index(index)
            if any(other is not user and (other.team, other.is_spy_master) == role.value for other in lobby.users):
                raise ValueError("Role is already occupied")
        if "name" in player_data:
            user.name = player_data["name"].strip()
        if "ready" in player_data:
            user.is_ready = player_data["ready"]
        if role:
            if (user.team, user.is_spy_master) != role.value and "ready" not in player_data:
                user.is_ready = False
            user.team, user.is_spy_master = role.value
        if player_data:
            lobby.revision += 1

        if lobby.ready_to_start():
            logger.info("Starting game...")
            await lobby.start_game()
        else:
            await lobby.send_player_update()
            

