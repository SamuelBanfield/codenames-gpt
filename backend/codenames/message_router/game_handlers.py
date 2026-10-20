from typing import Dict, Any, Optional, Tuple

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
                "serverMessageType": "stateError",
                "message": "User not in a lobby"
            }, None
            
        lobby: Optional[Lobby] = await self.lobby_service.get_lobby(user_context.lobby_id)
        if not lobby:
            return {
                "serverMessageType": "stateError",
                "message": "Lobby not found"
            }, None
        if user_context.user not in lobby.users:
            return {"serverMessageType": "stateError", "message": "User not in this lobby"}, None

        if not lobby.game:
            return {
                "serverMessageType": "stateError",
                "message": "Game not found"
            }, lobby
            
        return None, lobby


class InitialiseGameHandler(BaseGameHandler):
    """Handle game initialization requests"""

    async def handle(self, user_context: UserContext, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if not user_context.lobby_id:
            return {"serverMessageType": "stateError", "message": "User not in a lobby"}
        lobby = await self.lobby_service.get_lobby(user_context.lobby_id)
        if not lobby or user_context.user not in lobby.users:
            return {"serverMessageType": "stateError", "message": "Lobby membership not found"}
        if lobby.game:
            return lobby.game.get_state_update(user_context.user, False)
        return lobby.get_player_update()


class GuessTileHandler(BaseGameHandler):
    """Handle tile guesses"""

    async def handle(self, user_context: UserContext, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        error_response, lobby = await self._validate_context(user_context)
        if error_response:
            return error_response
        assert lobby is not None and lobby.game is not None, "For type checking"
        lobby.game.validate_action(data)
        
        word = data.get("word")
        if not isinstance(word, str) or not word.strip():
            return {
                "serverMessageType": "error",
                "message": "Missing word in guess"
            }
        return await lobby.game.guess_word(user_context.user, word)


class ProvideClueHandler(BaseGameHandler):
    """Handle clue provision"""

    async def handle(self, user_context: UserContext, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        error_response, lobby = await self._validate_context(user_context)
        if error_response:
            return error_response
        assert lobby is not None and lobby.game is not None, "For type checking"
        lobby.game.validate_action(data)
        
        word = data.get("word")
        number = data.get("number")
        if not word or number is None:
            return {
                "serverMessageType": "error",
                "message": "Missing word or number in clue"
            }
        if not await lobby.game.provide_clue(user_context.user, word, number):
            return lobby.game.get_state_update(user_context.user, False)


class RetryAIHandler(BaseGameHandler):
    async def handle(self, user_context: UserContext, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        error, lobby = await self._validate_context(user_context)
        if error:
            return error
        assert lobby is not None and lobby.game is not None
        lobby.game.validate_action(data)
        await lobby.game.retry_ai_turn()
