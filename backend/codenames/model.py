from enum import Enum
import logging
from typing import Optional
import uuid


class Role(Enum):
    """Enum for the different roles in the game"""
    RED_SPYMASTER = ("red", True)
    BLUE_SPYMASTER = ("blue", True)
    RED_OPERATIVE = ("red", False)
    BLUE_OPERATIVE = ("blue", False)
    
    @property
    def team(self) -> str:
        return self.value[0]
    
    @property
    def is_spymaster(self) -> bool:
        return self.value[1]
    
    @property
    def index(self) -> int:
        """Index as exposed to the frontend"""
        return list(Role).index(self)
    
    @classmethod
    def from_team_and_role(cls, team: str, is_spymaster: bool) -> 'Role':
        for role in cls:
            if role.team == team and role.is_spymaster == is_spymaster:
                return role
        raise ValueError(f"No role found for team={team}, is_spymaster={is_spymaster}")
    
    @classmethod
    def from_index(cls, index: int) -> 'Role':
        roles = list(cls)
        if 0 <= index < len(roles):
            return roles[index]
        raise ValueError(f"Invalid role index: {index}")
    
    @classmethod
    def all_roles(cls) -> list['Role']:
        return list(cls)


class CodenamesConnection:
    def __init__(self):
        self.uuid = uuid.uuid4()

    async def send(self, message: dict):
        raise NotImplementedError("Subclasses must implement this method")


class User:
    """Model of a user in the game"""
    def __init__(self, connection: CodenamesConnection, is_human: bool):
        self.name: str = ""
        self.connection: CodenamesConnection = connection
        self.is_spy_master: bool = False
        self.is_ready: bool = False
        self.in_game: bool = False
        self.in_lobby: bool = False
        self.team: Optional[str] = None
        self.is_human: bool = is_human

    async def send(self, message: dict):
        logging.info(f"Sending message to {self.name}: {message['serverMessageType']}")
        await self.connection.send(message)

    def to_json(self) -> dict:
        return {
            "name": self.name,
            "uuid": str(self.connection.uuid),
            "ready": self.is_ready,
            "inGame": self.in_game,
            "inLobby": self.in_lobby,
            "role": Role.from_team_and_role(self.team, self.is_spy_master).index if self.team else None
        }

class Tile:
    """Model of a tile in the game"""
    def __init__(self, word: str, team: str, is_revealed: bool = False):
        self.word = word
        self.revealed = is_revealed
        self.team = team

    def reveal(self):
        self.revealed = True

    def to_json(self, for_spymaster: bool) -> dict:
        return {
            "word": self.word,
            "revealed": self.revealed,
            "team": self.team if for_spymaster or self.revealed else "unknown"
        }


