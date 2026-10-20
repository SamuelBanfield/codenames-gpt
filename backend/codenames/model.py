from enum import Enum
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
    
class User:
    """Player identity and preferences, independent of any transport."""
    def __init__(self, is_human: bool = True, role: Optional[Role] = None):
        self.id = str(uuid.uuid4())
        self.name = ""
        self.role = role
        self.is_ready: bool = False
        self.is_human: bool = is_human

    @property
    def team(self) -> Optional[str]:
        return self.role.team if self.role else None

    @property
    def is_spy_master(self) -> bool:
        return self.role.is_spymaster if self.role else False

    def to_json(self, *, in_lobby: bool = False, in_game: bool = False) -> dict:
        return {
            "name": self.name,
            "uuid": self.id,
            "ready": self.is_ready,
            "inGame": in_game,
            "inLobby": in_lobby,
            "role": self.role.index if self.role else None,
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


