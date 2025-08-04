from typing import Dict, Any, Optional

from codenames.game import get_tile_by_word
from codenames.lobby import Lobby
from codenames.message_router.message_handler import UserContext
from codenames.services.lobby_service import LobbyService


class InitialiseGameHandler:
    """Handle game initialization requests"""
    def __init__(self, lobby_service: LobbyService):
        self.lobby_service = lobby_service

    async def handle(self, user_context: UserContext, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if not user_context.lobby_id:
            return {
                "serverMessageType": "error",
                "message": "User not in a lobby"
            }
        lobby: Optional[Lobby] = await self.lobby_service.get_lobby(user_context.lobby_id)
        if not lobby or not lobby.game:
            return {
                "serverMessageType": "error",
                "message": "Game not found"
            }
        await lobby.game.broadcast_state_update(False)

class GuessTileHandler:
    """Handle tile guesses"""
    def __init__(self, lobby_service: LobbyService):
        self.lobby_service = lobby_service

    async def handle(self, user_context: UserContext, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if not user_context.lobby_id:
            return {
                "serverMessageType": "error",
                "message": "User not in a lobby"
            }
        lobby: Optional[Lobby] = await self.lobby_service.get_lobby(user_context.lobby_id)
        if not lobby or not lobby.game:
            return {
                "serverMessageType": "error",
                "message": "Game not found"
            }
        word = data.get("word")
        if not word:
            return {
                "serverMessageType": "error",
                "message": "Missing word in guess"
            }
        await lobby.game.guess_tile(user_context.user, get_tile_by_word(word, lobby.game.tiles))

class ProvideClueHandler:
    """Handle clue provision"""
    def __init__(self, lobby_service: LobbyService):
        self.lobby_service = lobby_service

    async def handle(self, user_context: UserContext, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if not user_context.lobby_id:
            return {
                "serverMessageType": "error",
                "message": "User not in a lobby"
            }
        lobby: Optional[Lobby] = await self.lobby_service.get_lobby(user_context.lobby_id)
        if not lobby or not lobby.game:
            return {
                "serverMessageType": "error",
                "message": "Game not found"
            }
        word = data.get("word")
        number = data.get("number")
        if not word or number is None:
            return {
                "serverMessageType": "error",
                "message": "Missing word or number in clue"
            }
        await lobby.game.provide_clue(user_context.user, word, number)
