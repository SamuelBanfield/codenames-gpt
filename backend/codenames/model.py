from enum import Enum
from typing import Optional
import uuid
from codenames.options import VERBOSE_LOGGING


class Role(Enum):
    """Enum for the different roles in the game"""
    RED_SPYMASTER = ("red", True)
    BLUE_SPYMASTER = ("blue", True)
    RED_OPERATIVE = ("red", False)
    BLUE_OPERATIVE = ("blue", False)


class CodenamesConnection:
    def __init__(self):
        self.uuid = uuid.uuid4()

    async def send(self, message: dict):
        raise NotImplementedError("Subclasses must implement this method")


class User:
    """Model of a user in the game"""
    def __init__(self, connection: CodenamesConnection, is_human: bool):
        self.name = ""
        self.connection = connection
        self.is_spy_master = False
        self.is_ready = False
        self.in_game = False
        self.in_lobby = False
        self.team = None
        self.is_human = is_human

    async def send(self, message: dict):
        if VERBOSE_LOGGING:
            print(f"Sending message to {self.name}: {message['serverMessageType']}")
        await self.connection.send(message)

    def to_json(self) -> dict:
        return {
            "name": self.name,
            "uuid": str(self.connection.uuid),
            "ready": self.is_ready,
            "inGame": self.in_game,
            "inLobby": self.in_lobby,
            "role": self.get_role_index()
        }

    def get_role_index(self) -> Optional[Role]:
        if self.team is not None:
            return [role.value for role in Role].index((self.team, self.is_spy_master))
        return None

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


