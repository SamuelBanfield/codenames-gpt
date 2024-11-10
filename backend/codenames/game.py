
import asyncio
import pathlib
import random
from typing import List, Literal, Optional, Tuple

from codenames.model import CodenamesConnection, Role, Tile, User
from codenames.gpt.gpt_connection import GPTAgent

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
        self.gpt: GPTAgent = GPTAgent()

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
        if self.check_win():
            print("Ignoring guess as game is over")
            return
        if self.is_user_turn(user) and not user.is_spy_master:
            tile.reveal()
            may_continue: bool = self.update_guesses_remaining(tile, user)
            await self.broadcast_state_update(self.guesses_remaining <= 0)
            on_turn = self.get_on_turn_user()
            if not may_continue and not on_turn.is_human:
                clue, number = self.gpt.provide_clue(on_turn, self.tiles)
                await self.provide_clue(on_turn, clue, number)
        else:
            print(f"Ignoring guess from {user.name} as it is not their turn")

    def is_user_turn(self, user: User) -> bool:
        return self.current_turn.value == (user.team, user.is_spy_master)
    
    def get_on_turn_user(self) -> User:
        for user in self.users:
            if self.is_user_turn(user):
                return user
        raise ValueError("No user found for current turn")

    def update_guesses_remaining(self, tile: Tile, user: User) -> bool:
        """Returns true if the same user may guess again"""
        if tile.team == user.team:
            self.guesses_remaining -= 1
        else:
            self.guesses_remaining = 0
        if self.guesses_remaining <= 0:
            self.current_turn = Role(("red" if user.team == "blue" else "blue", True))
            self.clue = None
            return False
        return True

    async def provide_clue(self, user: User, word: str, number: int):
        if self.check_win():
            print("Ignoring guess as game is over")
            return
        if self.is_user_turn(user) and user.is_spy_master:
            self.clue = (word, number)
            self.guesses_remaining = number
            self.current_turn = Role((user.team, False))
            await self.broadcast_state_update(True)
            on_turn_user = self.get_on_turn_user()
            if not on_turn_user.is_human:
                guesses = self.gpt.make_guesses(word, number, self.tiles)
                while self.guesses_remaining > 0 and guesses:
                    await self.guess_tile(on_turn_user, get_tile_by_word(guesses.pop(0), self.tiles))
        else:
            print(f"Ignoring clue from {user.name} as it is not their turn")

    async def handle_request(self, user: User, message: dict):
        if "clientMessageType" not in message:
            raise ValueError("No message type specified")
        
        if self.check_win():
            print("Game is over, ignoring request")
            return

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
