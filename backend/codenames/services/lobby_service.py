from typing import Dict, List, Optional
import logging
from abc import ABC, abstractmethod

from codenames.lobby import Lobby
from codenames.model import Role, User
from codenames.game.factory import GameFactory
from codenames.game.runtime import GameRuntime
from codenames.gpt.chat_gpt import ChatGPT
from codenames.options import GUESS_DELAY
from codenames.services.connection_service import ConnectionManager

logger = logging.getLogger(__name__)

class LobbyRepository(ABC):
    """Abstract repository for lobby persistence"""
    
    @abstractmethod
    async def create_lobby(self, lobby: Lobby) -> None:
        pass
    
    @abstractmethod
    async def get_lobby(self, lobby_id: str) -> Optional[Lobby]:
        pass
    
    @abstractmethod
    async def list_lobbies(self) -> List[Lobby]:
        pass
    
    @abstractmethod
    async def update_lobby(self, lobby: Lobby) -> None:
        pass
    
    @abstractmethod
    async def delete_lobby(self, lobby_id: str) -> None:
        pass

class InMemoryLobbyRepository(LobbyRepository):
    """In-memory implementation of lobby repository"""
    
    def __init__(self):
        self._lobbies: Dict[str, Lobby] = {}
    
    async def create_lobby(self, lobby: Lobby) -> None:
        self._lobbies[str(lobby.id)] = lobby
        logger.info(f"Created lobby {lobby.id} with name '{lobby.name}'")
    
    async def get_lobby(self, lobby_id: str) -> Optional[Lobby]:
        return self._lobbies.get(lobby_id)
    
    async def list_lobbies(self) -> List[Lobby]:
        return list(self._lobbies.values())
    
    async def update_lobby(self, lobby: Lobby) -> None:
        if str(lobby.id) in self._lobbies:
            self._lobbies[str(lobby.id)] = lobby
            logger.debug(f"Updated lobby {lobby.id}")
    
    async def delete_lobby(self, lobby_id: str) -> None:
        if lobby_id in self._lobbies:
            lobby = self._lobbies.pop(lobby_id)
            logger.info(f"Deleted lobby {lobby_id} ('{lobby.name}')")

class LobbyService:
    """Domain service for lobby operations"""
    
    def __init__(self, repository: LobbyRepository, connections: ConnectionManager,
                 ai_factory=ChatGPT, guess_delay: float = GUESS_DELAY):
        self.repository = repository
        self.connections = connections
        self.ai_factory = ai_factory
        self.guess_delay = guess_delay

    def _set_membership(self, user: User, lobby_id: Optional[str]):
        session = self.connections.get_session(user.id)
        if session:
            session.lobby_id = lobby_id
    
    async def create_lobby(self, owner: User, name: str) -> Lobby:
        """Create a new lobby with the given owner and name"""
        await self._leave_previous_lobbies(owner)
        lobby = Lobby(owner, name)
        self._set_membership(owner, lobby.id)
        await self.repository.create_lobby(lobby)
        return lobby
    
    async def join_lobby(self, user: User, lobby_id: str) -> Optional[Lobby]:
        """Attempt to join a user to a lobby"""
        lobby = await self.repository.get_lobby(lobby_id)
        if not lobby:
            logger.warning(f"Attempt to join non-existent lobby: {lobby_id}")
            return None
        if user in lobby.users:
            self._set_membership(user, lobby.id)
            return lobby
        
        if lobby.game is not None:
            logger.info(f"Cannot join lobby {lobby_id}: game already started")
            return None
        
        if len(lobby.users) >= 4:
            logger.info(f"Cannot join lobby {lobby_id}: lobby is full")
            return None
        
        await self._leave_previous_lobbies(user)
        # Leaving an old game can await broadcasts/disposal. Revalidate the
        # destination after that suspension before occupying its last slot.
        lobby = await self.repository.get_lobby(lobby_id)
        if not lobby or lobby.game is not None or len(lobby.users) >= 4:
            return None
        lobby.users.append(user)
        lobby.revision += 1
        self._set_membership(user, lobby.id)
        await self.repository.update_lobby(lobby)
        logger.info(f"User {user.name} joined lobby {lobby_id}")
        return lobby
    
    async def leave_lobby(self, user: User, lobby_id: str) -> None:
        """Remove a user from a lobby and clean up if needed"""
        lobby = await self.repository.get_lobby(lobby_id)
        if not lobby:
            return
        
        if user not in lobby.users:
            logger.debug("User %s was not in lobby %s", user.id, lobby_id)
            return
        lobby.users = [other for other in lobby.users if other is not user]
        lobby.revision += 1
        humans_remain = any(other.is_human for other in lobby.users)
        on_turn = False
        if lobby.game:
            on_turn = lobby.game.remove_user(user, replace_with_ai=humans_remain)
        self._set_membership(user, None)
        user.is_ready = False
        user.role = None
        if not humans_remain:
            # Remove the room before awaiting cancellation/client shutdown.
            await self.repository.delete_lobby(lobby_id)
            if lobby.game:
                await lobby.game.dispose()
        else:
            if lobby.lobby_owner is user:
                lobby.lobby_owner = next(other for other in lobby.users if other.is_human)
            await self.repository.update_lobby(lobby)
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
        memberships = [lobby for lobby in await self.repository.list_lobbies() if user in lobby.users]
        if memberships:
            for lobby in memberships:
                await self.leave_lobby(user, str(lobby.id))
            user.is_ready = False
            user.role = None

    async def send_player_update(self, lobby: Lobby):
        message = lobby.get_player_update()
        await self.connections.broadcast(lobby.users, lambda user: message)

    async def start_game(self, lobby: Lobby):
        if lobby.game is not None:
            return
        game = GameRuntime(GameFactory.create_game(lobby.users), self.connections,
                           self.ai_factory, self.guess_delay)
        lobby.game = game
        lobby.revision += 1
        game.lobby_id = lobby.id
        game.started = False
        await self.send_player_update(lobby)
        if game.disposed:
            return
        game.started = True
        game.state.revision += 1
        turn = game.state.turn_id
        await game.broadcast_state_update(True)
        game.schedule_ai_turn(turn)

    async def update_preferences(self, user: User, lobby_id: str, player_data: dict):
        lobby = await self.get_lobby(lobby_id)
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
    
    async def get_available_lobbies(self) -> List[Lobby]:
        """Get all lobbies that can be joined"""
        all_lobbies = await self.repository.list_lobbies()
        return [lobby for lobby in all_lobbies 
                if lobby.game is None and len(lobby.users) < 4]
    
    async def get_lobby(self, lobby_id: str) -> Optional[Lobby]:
        """Get a specific lobby by ID"""
        return await self.repository.get_lobby(lobby_id)
