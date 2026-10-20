from codenames.message_router.message_handler import UserContext
from codenames.services.lobby_service import LobbyService


class UpdatePreferencesHandler:
    def __init__(self, lobby_service: LobbyService):
        self.lobby_service = lobby_service

    async def handle(self, user_context: UserContext, data: dict):
        if not user_context.lobby_id:
            return {"serverMessageType": "stateError", "message": "User not in a lobby"}
        lobby = await self.lobby_service.get_lobby(user_context.lobby_id)
        if not lobby:
            return {"serverMessageType": "stateError", "message": "Lobby not found"}
        if user_context.user not in lobby.users:
            return {"serverMessageType": "stateError", "message": "User not in this lobby"}
        await self.lobby_service.update_preferences(
            user_context.user, user_context.lobby_id, data.get("player", {}),
        )
