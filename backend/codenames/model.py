import asyncio
import json
import pathlib
import random
import uuid
from typing import List, Literal, Optional

from codenames.options import VERBOSE_LOGGING

# Yuck
ROLES = [("red", True), ("blue", True), ("red", False), ("blue", False)]

class CodenamesGameResult:
    RED_WIN = "red"
    BLUE_WIN = "blue"

class CodenamesConnection:

    def __init__(self):
        self.uuid = uuid.uuid4()

    async def send(self, message):
        raise NotImplementedError("Subclasses must implement this method")

class User:

    def __init__(self, connection: CodenamesConnection):
        self.name = ""
        self.connection = connection
        self.is_spy_master = False
        self.is_ready = False
        self.in_game = False
        self.team = None

    async def send(self, message):
        if VERBOSE_LOGGING:
            print(f"Sending message to {self.name}: {message['serverMessageType']}")
        await self.connection.send(message)

    def __json__(self):
        return {
            "name": self.name,
            "uuid": str(self.connection.uuid),
            "ready": self.is_ready,
            "inGame": self.in_game,
            "role": ROLES.index((self.team, self.is_spy_master)) if self.team is not None else None
        }

class Tile:

    def __init__(self, word, team, is_revealed=False):
        self.word = word
        self.revealed = is_revealed
        self.team = team

    def reveal(self):
        self.revealed = True

    def get_json(self, for_spymaster: bool):
        return {
            "word": self.word,
            "revealed": self.revealed,
            "team": self.team if for_spymaster or self.revealed else "unknown"
        }

def _generate_tiles():
    with open(pathlib.Path(__file__).parent 
              / ".." / "wordlist.txt") as f:
        words = f.readlines()
    used_words = random.sample(words, 25)
    red_tiles = [Tile(word.replace("\n", ""), "red") for word in used_words[:9]]
    blue_words = [Tile(word.replace("\n", ""), "blue") for word in used_words[9:17]]
    assassin_word = [Tile(used_words[17].replace("\n", ""), "assassin")]
    neutral_words = [Tile(word.replace("\n", ""), "neutral") for word in used_words[18:25]]
    all_words = red_tiles + blue_words + assassin_word + neutral_words
    random.shuffle(all_words)
    return all_words

def get_tile_by_word(word, tiles):
    for tile in tiles:
        if tile.word.replace(" ", "").lower() == word.replace(" ", "").lower():
            return tile
    raise Exception(f"No tile found for word {word}")

class CodenamesGame:

    def __init__(self, users: List[User]):
        self.users: List[User] = users
        self._tiles = _generate_tiles()
        self.current_turn = 0 # Index in ROLES on turn role
        self.guesses_remaining = 0
        self.clue = None # Tuple of (word, number)

    async def _broadcast_state_update(self, is_on_turn_update):
        await asyncio.gather(*(user.send({
                "serverMessageType": "stateUpdate",
                "tiles": [
                    tile.get_json(user.is_spy_master) for tile in self._tiles
                ],
                "players": [user.__json__() for user in self.users],
                "onTurnRole": self.current_turn,
                "guessesRemaining": self.guesses_remaining,
                "clue": {"word": self.clue[0].upper(), "number": self.clue[1]} if self.clue else None,
                "new_turn": is_on_turn_update
            }) for user in self.users))
        
    def check_win(self) -> Optional[Literal["red", "blue"]]:
        if not [tile for tile in self._tiles if tile.team == "red" and not tile.revealed]:
            return "red"
        if not [tile for tile in self._tiles if tile.team == "blue" and not tile.revealed]:
            return "blue"
        if [tile for tile in self._tiles if tile.team == "assassin" and tile.revealed]:
            return "red" if ROLES[self.current_turn][0] == "blue" else "blue"

    async def guess_tile(self, user: User, tile) -> Optional[Literal["red", "blue"]]:
        if self.current_turn == ROLES.index((user.team, user.is_spy_master)) and not user.is_spy_master:
            tile.reveal()
            if winner := self.check_win():
                return winner
            if tile.team == "assassin":
                # Lose the game
                self.guesses_remaining = 0
            elif tile.team == user.team:
                self.guesses_remaining -= 1
            else:
                self.guesses_remaining = 0
            if self.guesses_remaining <= 0:
                self.current_turn = ROLES.index(("red" if user.team == "blue" else "blue", True))
                self.clue = None
            await self._broadcast_state_update(self.guesses_remaining <= 0)
        else:
            print(f"Ignoring guess from {user.name} as it is not their turn")

    async def provide_clue(self, user, word, number):
        if self.current_turn == ROLES.index((user.team, user.is_spy_master)) and user.is_spy_master:
            self.clue = (word, number)
            self.guesses_remaining = number
            self.current_turn = ROLES.index((user.team, False))
            await self._broadcast_state_update(True) 
            return self.clue
        else:
            print(f"Ignoring clue from {user.name} as it is not their turn")

    async def request(self, user: User, message: json):
        if not "clientMessageType" in message:
            raise Exception("No message type specified")
        
        match message["clientMessageType"]:
            case "initialiseRequest":
                await self._broadcast_state_update(False)
            case "guessTile":
                await self.guess_tile(user, get_tile_by_word(message["word"], self._tiles))
            case "provideClue":
                await self.provide_clue(user, message["word"], message["number"])
            case _:
                raise Exception("Unknown request type")
            
    async def pass_turn(self, user: User):
        if self.current_turn == ROLES.index((user.team, user.is_spy_master)) and not user.is_spy_master:
            self.guesses_remaining = 0
            self.current_turn = ROLES.index(("red" if user.team == "blue" else "blue", True))
            self.clue = None
            await self._broadcast_state_update(self.guesses_remaining <= 0)
            
    def get_user_by_connection(self, connection: CodenamesConnection):
        for user in self.users:
            if user.connection == connection:
                return user
        raise Exception(f"No user found for connection {connection}")
