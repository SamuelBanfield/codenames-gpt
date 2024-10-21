import asyncio
import pathlib
import random
import uuid
from enum import Enum
from typing import List, Literal, Optional, Tuple

from codenames.options import VERBOSE_LOGGING

class Role(Enum):
    RED_SPYMASTER = ("red", True)
    BLUE_SPYMASTER = ("blue", True)
    RED_OPERATIVE = ("red", False)
    BLUE_OPERATIVE = ("blue", False)

class GameResult(Enum):
    RED_WIN = "red"
    BLUE_WIN = "blue"

class CodenamesConnection:
    def __init__(self):
        self.uuid = uuid.uuid4()

    async def send(self, message: dict):
        raise NotImplementedError("Subclasses must implement this method")

class User:
    def __init__(self, connection: CodenamesConnection):
        self.name = ""
        self.connection = connection
        self.is_spy_master = False
        self.is_ready = False
        self.in_game = False
        self.team = None

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
            "role": self.get_role_index()
        }

    def get_role_index(self) -> Optional[Role]:
        if self.team is not None:
            return [role.value for role in Role].index((self.team, self.is_spy_master))
        return None

class Tile:
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

def generate_tiles() -> List[Tile]:
    with open(pathlib.Path(__file__).parent / ".." / "wordlist.txt") as f:
        words = f.readlines()
    used_words = random.sample(words, 25)
    red_tiles = [Tile(word.strip(), "red") for word in used_words[:9]]
    blue_tiles = [Tile(word.strip(), "blue") for word in used_words[9:17]]
    assassin_tile = [Tile(used_words[17].strip(), "assassin")]
    neutral_tiles = [Tile(word.strip(), "neutral") for word in used_words[18:25]]
    all_tiles = red_tiles + blue_tiles + assassin_tile + neutral_tiles
    random.shuffle(all_tiles)
    return all_tiles

def get_tile_by_word(word: str, tiles: List[Tile]) -> Tile:
    for tile in tiles:
        if tile.word.replace(" ", "").lower() == word.replace(" ", "").lower():
            return tile
    raise ValueError(f"No tile found for word {word}")

class CodenamesGame:
    def __init__(self, users: List[User]):
        self.users = users
        self.tiles = generate_tiles()
        self.current_turn: Role = Role.RED_SPYMASTER
        self.guesses_remaining = 0
        self.clue: Optional[Tuple[str, int]] = None

    async def broadcast_state_update(self, is_on_turn_update: bool):
        await asyncio.gather(*(user.send(self.get_state_update(user, is_on_turn_update)) for user in self.users))

    def get_state_update(self, user: User, is_on_turn_update: bool) -> dict:
        return {
            "serverMessageType": "stateUpdate",
            "tiles": [tile.to_json(user.is_spy_master) for tile in self.tiles],
            "players": [u.to_json() for u in self.users],
            "onTurnRole": [role for role in Role].index(self.current_turn),
            "guessesRemaining": self.guesses_remaining,
            "clue": {"word": self.clue[0].upper(), "number": self.clue[1]} if self.clue else None,
            "new_turn": is_on_turn_update,
            "winner": self.check_win()
        }

    def check_win(self) -> Optional[Literal["red", "blue"]]:
        if not any(tile.team == "red" and not tile.revealed for tile in self.tiles):
            return "red"
        if not any(tile.team == "blue" and not tile.revealed for tile in self.tiles):
            return "blue"
        if any(tile.team == "assassin" and tile.revealed for tile in self.tiles):
            return "red" if self.current_turn.value[0] == "blue" else "blue"
        return None

    async def guess_tile(self, user: User, tile: Tile) -> Optional[Literal["red", "blue"]]:
        if self.is_user_turn(user) and not user.is_spy_master:
            tile.reveal()
            winner = self.check_win()
            if winner:
                return winner
            self.update_guesses_remaining(tile, user)
            await self.broadcast_state_update(self.guesses_remaining <= 0)
        else:
            print(f"Ignoring guess from {user.name} as it is not their turn")

    def is_user_turn(self, user: User) -> bool:
        return self.current_turn.value == (user.team, user.is_spy_master)

    def update_guesses_remaining(self, tile: Tile, user: User):
        if tile.team == "assassin":
            self.guesses_remaining = 0
        elif tile.team == user.team:
            self.guesses_remaining -= 1
        else:
            self.guesses_remaining = 0
        if self.guesses_remaining <= 0:
            self.current_turn = Role(("red" if user.team == "blue" else "blue", True))
            self.clue = None

    async def provide_clue(self, user: User, word: str, number: int):
        if self.is_user_turn(user) and user.is_spy_master:
            self.clue = (word, number)
            self.guesses_remaining = number
            self.current_turn = Role((user.team, False))
            await self.broadcast_state_update(True)
        else:
            print(f"Ignoring clue from {user.name} as it is not their turn")

    async def handle_request(self, user: User, message: dict):
        if "clientMessageType" not in message:
            raise ValueError("No message type specified")

        match message["clientMessageType"]:
            case "initialiseRequest":
                await self.broadcast_state_update(False)
            case "guessTile":
                await self.guess_tile(user, get_tile_by_word(message["word"], self.tiles))
            case "provideClue":
                await self.provide_clue(user, message["word"], message["number"])
            case _:
                raise ValueError("Unknown request type")

    async def pass_turn(self, user: User):
        if self.is_user_turn(user) and not user.is_spy_master:
            self.guesses_remaining = 0
            self.current_turn = Role(("red" if user.team == "blue" else "blue", True))
            self.clue = None
            await self.broadcast_state_update(True)

    def get_user_by_connection(self, connection: CodenamesConnection) -> User:
        for user in self.users:
            if user.connection == connection:
                return user
        raise ValueError(f"No user found for connection {connection}")
