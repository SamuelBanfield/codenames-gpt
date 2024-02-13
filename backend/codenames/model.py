import json
import pathlib
import random
from typing import List, Literal
import uuid

# Yuck
ROLES = [("red", True), ("blue", True), ("red", False), ("blue", False)]

class CodenamesConnection:

    def __init__(self):
        self.uuid = uuid.uuid4()

    def send(self, message):
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
        print(f"Sending message to {self.name}: {message}")
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

    def __json__(self):
        return {
            "word": self.word,
            "revealed": self.revealed,
            "team": self.team
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

def _get_tile_by_word(word, tiles):
    for tile in tiles:
        if tile.word == word:
            return tile
    raise Exception(f"No tile found for word {word}")

class CodenamesGame:

    def __init__(self, users: List[User]):
        self.users: List[User] = users
        self._tiles = _generate_tiles()
        self.current_turn = 0 # Index in ROLES on turn role
        self.guesses_remaining = 0
        self.clue = None # Tuple of (word, number)

    async def send_game_message_to_all(self, message):
        print(f"Sending game message to all: {message["serverMessageType"]}")
        for user in self.users:
            await user.connection.send(json.dumps(message))

    async def _broadcast_state_update(self):
        # This is actually sort of wrong, as the information should vary by role
        await self.send_game_message_to_all({
            "serverMessageType": "stateUpdate",
            "tiles": [
                tile.__json__() for tile in self._tiles
            ],
            "players": [user.__json__() for user in self.users],
            "onTurnRole": self.current_turn,
            "guessesRemaining": self.guesses_remaining,
            "clue": {"word": self.clue[0], "number": self.clue[1]} if self.clue else None
        })

    async def guess_tile(self, user: User, tile):
        if self.current_turn == ROLES.index((user.team, user.is_spy_master)) and not user.is_spy_master:
            tile.reveal()
            if tile.team == "assassin":
                # Lose the game
                self.guesses_remaining = 0
            elif tile.team == user.team:
                self.guesses_remaining -= 1
            else:
                self.guesses_remaining = 0
            if self.guesses_remaining == 0:
                self.current_turn = ROLES.index(("red" if user.team == "blue" else "blue", True))
                self.clue = None
            await self._broadcast_state_update()
        else:
            print(f"Ignoring guess from {user.name} as it is not their turn")

    async def provide_clue(self, user, word, number):
        if self.current_turn == ROLES.index((user.team, user.is_spy_master)) and user.is_spy_master:
            self.clue = (word, number)
            self.current_turn = ROLES.index((user.team, False))
            await self._broadcast_state_update()
        else:
            print(f"Ignoring clue from {user.name} as it is not their turn")

    async def request(self, user: User, message: json):
        if not "clientMessageType" in message:
            raise Exception("No message type specified")
        
        match message["clientMessageType"]:
            case "initialiseRequest":
                await self._broadcast_state_update()
            case "guessTile":
                await self.guess_tile(user, _get_tile_by_word(message["word"], self._tiles))
            case "provideClue":
                await self.provide_clue(user, message["word"], message["number"])
            case _:
                raise Exception("Unknown request type")
