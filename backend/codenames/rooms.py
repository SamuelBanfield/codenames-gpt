"""Own live rooms and coordinate membership, readiness, and game lifetime."""

import asyncio
import logging
from typing import Optional

from codenames.connections import Connections
from codenames.game.factory import create_game
from codenames.game.runtime import GameRuntime
from codenames.lobby import Lobby
from codenames.model import Role, User

logger = logging.getLogger(__name__)


class Rooms:
    def __init__(self, connections: Connections, ai_factory, guess_delay: float):
        self.connections = connections
        self.ai_factory = ai_factory
        self.guess_delay = guess_delay
        self._lobbies: dict[str, Lobby] = {}
        self._stopping = False

    def _require_running(self):
        if self._stopping:
            raise ValueError("Server is shutting down")

    async def shutdown(self):
        """Retire rooms before awaiting cleanup; never run normal departure/start logic."""
        self._stopping = True
        lobbies = self.list_lobbies()
        self._lobbies.clear()
        for lobby in lobbies:
            for user in lobby.users:
                self._set_membership(user, None)
                user.is_ready = False
                user.role = None
        results = await asyncio.gather(
            *(lobby.game.dispose() for lobby in lobbies if lobby.game), return_exceptions=True,
        )
        for result in results:
            if isinstance(result, BaseException):
                logger.error("Game cleanup failed during shutdown",
                             exc_info=(type(result), result, result.__traceback__))

    def get_lobby(self, lobby_id: str) -> Optional[Lobby]:
        return self._lobbies.get(lobby_id)

    def list_lobbies(self) -> list[Lobby]:
        return list(self._lobbies.values())

    def get_available_lobbies(self) -> list[Lobby]:
        return [lobby for lobby in self._lobbies.values()
                if lobby.game is None and len(lobby.users) < 4]

    def _set_membership(self, user: User, lobby_id: Optional[str]):
        session = self.connections.get_session(user.id)
        if session:
            session.lobby_id = lobby_id

    async def create_lobby(self, user: User, name: str) -> Lobby:
        self._require_running()
        await self._leave_previous_lobbies(user)
        self._require_running()
        lobby = Lobby(user, name)
        self._lobbies[lobby.id] = lobby
        self._set_membership(user, lobby.id)
        logger.info("Created lobby %s", lobby.id)
        return lobby

    async def join_lobby(self, user: User, lobby_id: str) -> Optional[Lobby]:
        self._require_running()
        lobby = self.get_lobby(lobby_id)
        if not lobby:
            return None
        if user in lobby.users:
            self._set_membership(user, lobby.id)
            return lobby
        if lobby.game is not None or len(lobby.users) >= 4:
            return None
        await self._leave_previous_lobbies(user)
        self._require_running()
        # Old-room delivery/disposal can suspend; the destination may change.
        lobby = self.get_lobby(lobby_id)
        if not lobby or lobby.game is not None or len(lobby.users) >= 4:
            return None
        lobby.users.append(user)
        lobby.revision += 1
        self._set_membership(user, lobby.id)
        logger.info("User %s joined lobby %s", user.id, lobby_id)
        return lobby

    async def leave_lobby(self, user: User, lobby_id: str) -> None:
        lobby = self.get_lobby(lobby_id)
        if not lobby or user not in lobby.users:
            return
        lobby.users.remove(user)
        lobby.revision += 1
        humans_remain = any(other.is_human for other in lobby.users)
        on_turn = lobby.game.remove_user(user, replace_with_ai=humans_remain) if lobby.game else False
        self._set_membership(user, None)
        user.is_ready = False
        user.role = None
        if not humans_remain:
            # Retire membership/room state before awaiting AI cleanup.
            del self._lobbies[lobby_id]
            if lobby.game:
                await lobby.game.dispose()
            logger.info("Deleted lobby %s", lobby_id)
            return
        if lobby.game:
            turn = lobby.game.state.turn_id
            await lobby.game.broadcast_state_update(False)
            if on_turn:
                lobby.game.schedule_ai_turn(turn)
        if lobby.ready_to_start():
            await self.start_game(lobby)
        else:
            await self.send_player_update(lobby)

    async def _leave_previous_lobbies(self, user: User):
        for lobby in self.list_lobbies():
            if user in lobby.users:
                await self.leave_lobby(user, lobby.id)

    async def send_player_update(self, lobby: Lobby):
        message = lobby.get_player_update()
        await self.connections.broadcast(lobby.users, lambda user: message)

    async def start_game(self, lobby: Lobby):
        self._require_running()
        if lobby.game is not None:
            return
        game = GameRuntime(create_game(lobby.users), self.connections, self.ai_factory,
                           self.guess_delay, lobby_id=lobby.id)
        lobby.game = game
        lobby.revision += 1
        await self.send_player_update(lobby)
        await game.activate()

    async def update_preferences(self, user: User, lobby_id: str, player_data: dict):
        self._require_running()
        lobby = self.get_lobby(lobby_id)
        if not lobby or user not in lobby.users:
            raise ValueError("User not in this lobby")
        if not isinstance(player_data, dict):
            raise ValueError("Player preferences must be an object")
        if lobby.game:
            if player_data:
                raise ValueError("Preferences cannot change after game startup")
            await self.send_player_update(lobby)
            return
        if "name" in player_data and (not isinstance(player_data["name"], str) or not player_data["name"].strip()):
            raise ValueError("Name must be a nonempty string")
        if "ready" in player_data and type(player_data["ready"]) is not bool:
            raise ValueError("Ready must be a boolean")
        role = None
        if player_data.get("role") is not None:
            if type(player_data["role"]) is not int:
                raise ValueError("Role must be an integer")
            role = Role.from_index(player_data["role"])
            if any(other is not user and other.role == role for other in lobby.users):
                raise ValueError("Role is already occupied")
        if "name" in player_data:
            user.name = player_data["name"].strip()
        if "ready" in player_data:
            user.is_ready = player_data["ready"]
        if role:
            if user.role != role and "ready" not in player_data:
                user.is_ready = False
            user.role = role
        if player_data:
            lobby.revision += 1
        if lobby.ready_to_start():
            await self.start_game(lobby)
        else:
            await self.send_player_update(lobby)
