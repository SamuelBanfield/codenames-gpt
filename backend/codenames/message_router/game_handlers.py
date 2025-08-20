from typing import Dict, Any, Optional, Tuple

from codenames.util import get_tile_by_word
from codenames.game.game import CodenamesGame
from codenames.lobby import Lobby
from codenames.message_router.message_handler import UserContext
from codenames.services.lobby_service import LobbyService


class BaseGameHandler:
    """Base class for game message handlers"""
    def __init__(self, lobby_service: LobbyService):
        self.lobby_service = lobby_service

    async def _validate_context(self, user_context: UserContext) -> Tuple[Optional[Dict[str, Any]], Optional[Lobby]]:
        """Common validation logic - returns (error_response, lobby)"""
        if not user_context.lobby_id:
            return {
                "serverMessageType": "error",
                "message": "User not in a lobby"
            }, None
            
        lobby: Optional[Lobby] = await self.lobby_service.get_lobby(user_context.lobby_id)
        if not lobby:
            return {
                "serverMessageType": "error",
                "message": "Lobby not found"
            }, None

        if not lobby.game:
            return {
                "serverMessageType": "error",
                "message": "Game not found"
            }, lobby
            
        return None, lobby


class InitialiseGameHandler(BaseGameHandler):
    """Handle game initialization requests"""

    async def handle(self, user_context: UserContext, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        error_response, lobby = await self._validate_context(user_context)
        if error_response:
            return error_response
        assert lobby is not None and lobby.game is not None, "For type checking"
        if lobby and data.get("includeUserInfo"):
            await lobby.send_player_update()

        await lobby.game.broadcast_state_update(False)


class GuessTileHandler(BaseGameHandler):
    """Handle tile guesses"""

    async def handle(self, user_context: UserContext, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        error_response, lobby = await self._validate_context(user_context)
        if error_response:
            return error_response
        assert lobby is not None and lobby.game is not None, "For type checking"
        
        word = data.get("word")
        if not word:
            return {
                "serverMessageType": "error",
                "message": "Missing word in guess"
            }
        await lobby.game.guess_tile(user_context.user, get_tile_by_word(word, lobby.game.tiles))


class ProvideClueHandler(BaseGameHandler):
    """Handle clue provision"""

    async def handle(self, user_context: UserContext, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        error_response, lobby = await self._validate_context(user_context)
        if error_response:
            return error_response
        assert lobby is not None and lobby.game is not None, "For type checking"
        
        word = data.get("word")
        number = data.get("number")
        if not word or number is None:
            return {
                "serverMessageType": "error",
                "message": "Missing word or number in clue"
            }
        await lobby.game.provide_clue(user_context.user, word, number)
