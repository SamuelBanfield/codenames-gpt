"""Player-protocol dispatch; room/game rules live outside this transport boundary."""

import logging
from typing import Optional

from codenames.connections import Session
from codenames.lobby import Lobby
from codenames.rooms import Rooms

logger = logging.getLogger(__name__)


class MessageRouter:
    def __init__(self, rooms: Rooms):
        self.rooms = rooms
        self.handlers = {
            "idRequest": self.id_request,
            "createLobby": self.create_lobby,
            "joinLobby": self.join_lobby,
            "lobbiesRequest": self.lobbies_request,
            "leaveLobby": self.leave_lobby,
            "preferencesRequest": self.preferences_request,
            "initialiseRequest": self.initialise_request,
            "guessTile": self.guess_tile,
            "provideClue": self.provide_clue,
            "retryAI": self.retry_ai,
        }

    async def route_message(self, session: Session, message_type: str, data: dict) -> Optional[dict]:
        handler = self.handlers.get(message_type)
        if handler is None:
            logger.warning("No handler for message type: %s", message_type)
            return {"serverMessageType": "error", "message": f"Unknown message type: {message_type}"}
        try:
            return await handler(session, data)
        except ValueError as error:
            return {"serverMessageType": "error", "message": str(error), "code": "invalidRequest"}
        except Exception:
            logger.exception("Error handling message %s", message_type)
            return {"serverMessageType": "error", "message": "Internal server error"}

    def _lobby_context(self, session: Session, *, require_game: bool = False) -> tuple[Optional[dict], Optional[Lobby]]:
        if not session.lobby_id:
            return {"serverMessageType": "stateError", "message": "User not in a lobby"}, None
        lobby = self.rooms.get_lobby(session.lobby_id)
        if not lobby:
            return {"serverMessageType": "stateError", "message": "Lobby not found"}, None
        if session.user not in lobby.users:
            return {"serverMessageType": "stateError", "message": "User not in this lobby"}, None
        if require_game and lobby.game is None:
            return {"serverMessageType": "stateError", "message": "Game not found"}, None
        return None, lobby

    async def id_request(self, session: Session, data: dict) -> dict:
        return {"serverMessageType": "idAssign", "uuid": session.user.id}

    async def create_lobby(self, session: Session, data: dict) -> dict:
        name = data.get("name", "Unnamed Lobby")
        if not isinstance(name, str) or not name.strip():
            raise ValueError("Lobby name must be a nonempty string")
        lobby = await self.rooms.create_lobby(session.user, name)
        return {"serverMessageType": "lobbyJoined", "lobbyId": lobby.id}

    async def join_lobby(self, session: Session, data: dict) -> dict:
        lobby_id = data.get("lobbyId")
        if not lobby_id:
            raise ValueError("Missing lobbyId in join request")
        lobby = await self.rooms.join_lobby(session.user, lobby_id)
        if lobby:
            return {"serverMessageType": "lobbyJoined", "lobbyId": lobby.id}
        return {"serverMessageType": "error", "message": "Unable to join lobby"}

    async def lobbies_request(self, session: Session, data: dict) -> dict:
        return {"serverMessageType": "lobbiesUpdate",
                "lobbies": [lobby.to_json() for lobby in self.rooms.get_available_lobbies()]}

    async def leave_lobby(self, session: Session, data: dict) -> dict:
        if session.lobby_id:
            await self.rooms.leave_lobby(session.user, session.lobby_id)
        return {"serverMessageType": "lobbyLeft"}

    async def preferences_request(self, session: Session, data: dict):
        error, lobby = self._lobby_context(session)
        if error:
            return error
        await self.rooms.update_preferences(session.user, lobby.id, data.get("player", {}))

    async def initialise_request(self, session: Session, data: dict) -> dict:
        error, lobby = self._lobby_context(session)
        if error:
            # Preserve the existing initialization-specific context error.
            if session.lobby_id:
                return {"serverMessageType": "stateError", "message": "Lobby membership not found"}
            return error
        return lobby.game.get_state_update(session.user, False) if lobby.game else lobby.get_player_update()

    async def guess_tile(self, session: Session, data: dict):
        error, lobby = self._lobby_context(session, require_game=True)
        if error:
            return error
        lobby.game.validate_action(data)
        word = data.get("word")
        if not isinstance(word, str) or not word.strip():
            return {"serverMessageType": "error", "message": "Missing word in guess"}
        return await lobby.game.guess_word(session.user, word)

    async def provide_clue(self, session: Session, data: dict):
        error, lobby = self._lobby_context(session, require_game=True)
        if error:
            return error
        lobby.game.validate_action(data)
        word, number = data.get("word"), data.get("number")
        if not word or number is None:
            return {"serverMessageType": "error", "message": "Missing word or number in clue"}
        if not await lobby.game.provide_clue(session.user, word, number):
            return lobby.game.get_state_update(session.user, False)

    async def retry_ai(self, session: Session, data: dict):
        error, lobby = self._lobby_context(session, require_game=True)
        if error:
            return error
        lobby.game.validate_action(data)
        await lobby.game.retry_ai_turn()
