from typing import Dict, List, Optional
import logging
from abc import ABC, abstractmethod

from codenames.lobby import Lobby
from codenames.model import User

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
    
    def __init__(self, repository: LobbyRepository):
        self.repository = repository
    
    async def create_lobby(self, owner: User, name: str) -> Lobby:
        """Create a new lobby with the given owner and name"""
        lobby = Lobby(owner, name)
        await self.repository.create_lobby(lobby)
        return lobby
    
    async def join_lobby(self, user: User, lobby_id: str) -> Optional[Lobby]:
        """Attempt to join a user to a lobby"""
        lobby = await self.repository.get_lobby(lobby_id)
        if not lobby:
            logger.warning(f"Attempt to join non-existent lobby: {lobby_id}")
            return None
        
        if lobby.game is not None:
            logger.info(f"Cannot join lobby {lobby_id}: game already started")
            return None
        
        if len(lobby.users) >= 4:
            logger.info(f"Cannot join lobby {lobby_id}: lobby is full")
            return None
        
        lobby.add_user(user)
        await self.repository.update_lobby(lobby)
        logger.info(f"User {user.name} joined lobby {lobby_id}")
        return lobby
    
    async def leave_lobby(self, user: User, lobby_id: str) -> None:
        """Remove a user from a lobby and clean up if needed"""
        lobby = await self.repository.get_lobby(lobby_id)
        if not lobby:
            return
        
        try:
            lobby.users.remove(user)
            await self.repository.update_lobby(lobby)
            
            # Clean up empty lobbies with no human players
            if not any(u.is_human for u in lobby.users):
                await self.repository.delete_lobby(lobby_id)
                logger.info(f"Cleaned up empty lobby {lobby_id}")
        except ValueError:
            logger.debug(f"User {user.connection.uuid} was not in lobby {lobby_id}")
    
    async def get_available_lobbies(self) -> List[Lobby]:
        """Get all lobbies that can be joined"""
        all_lobbies = await self.repository.list_lobbies()
        return [lobby for lobby in all_lobbies 
                if lobby.game is None and len(lobby.users) < 4]
