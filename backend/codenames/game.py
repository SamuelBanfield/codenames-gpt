
import asyncio
import pathlib
import random
import time
from typing import List, Literal, Optional, Tuple

from codenames.options import GUESS_DELAY
from codenames.model import Role, Tile, User
from codenames.gpt.gpt_connection import GPTAgent

def generate_tiles() -> List[Tile]:
    with open(pathlib.Path(__file__).parent / ".." / "wordlist.txt") as f:
        words = f.readlines()
    used_words = random.sample(words, 25)
    teams = ["red"] * 9 + ["blue"] * 8 + ["assassin"] + ["neutral"] * 7
    all_tiles = [Tile(word.strip(), team) for word, team in zip(used_words, teams)]
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
            return self.current_turn.value[0]
        return None

    async def guess_tile(self, user: User, tile: Tile) -> Optional[Literal["red", "blue"]]:
        if self.check_win():
            print("Ignoring guess as game is over")
            return
        if self.is_user_turn(user) and not user.is_spy_master:
            tile.reveal()
            may_continue: bool = self.update_guesses_remaining(tile, user)
            await self.broadcast_state_update(self.guesses_remaining <= 0)
            # Get the on_turn user AFTER potentially switching turns
            on_turn = self.get_on_turn_user()
            if not may_continue and not on_turn.is_human:
                # Schedule AI clue asynchronously to avoid blocking human input
                asyncio.create_task(self._handle_ai_clue(on_turn))
        else:
            print(f"Ignoring guess from {user.name} as it is not their turn")

    async def _handle_ai_clue(self, user: User):
        """Handle AI clue generation asynchronously to avoid blocking human input"""
        try:
            clue, number = await self.gpt.provide_clue(user, self.tiles)
            await asyncio.sleep(GUESS_DELAY)
            await self.provide_clue(user, clue, number)
        except Exception as e:
            print(f"Error in AI clue generation for {user.name}: {e}")

    async def _handle_ai_guessing(self, word: str, number: int, user: User):
        """Handle AI guessing asynchronously to avoid blocking human input"""
        try:
            guesses = await self.gpt.make_guesses(word, number, self.tiles)
            if not guesses:
                await self.pass_turn(user)
                return
                
            while self.guesses_remaining > 0 and guesses:
                await asyncio.sleep(GUESS_DELAY)
                guess_word = guesses.pop(0)
                try:
                    tile = get_tile_by_word(guess_word, self.tiles)
                    await self.guess_tile(user, tile)
                except ValueError:
                    print(f"AI {user.name} guessed invalid word: {guess_word}")
                    # Skip this invalid guess and continue with the next one
                    continue
        except Exception as e:
            print(f"Error in AI guessing for {user.name}: {e}")


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
                # Schedule AI guessing asynchronously to avoid blocking human input
                asyncio.create_task(self._handle_ai_guessing(word, number, on_turn_user))
        else:
            print(f"Ignoring clue from {user.name} as it is not their turn")

    async def pass_turn(self, user: User):
        if self.is_user_turn(user) and not user.is_spy_master:
            self.guesses_remaining = 0
            self.current_turn = Role(("red" if user.team == "blue" else "blue", True))
            self.clue = None
            await self.broadcast_state_update(True)
            on_turn = self.get_on_turn_user()
            if not on_turn.is_human:
                # Schedule AI clue asynchronously to avoid blocking human input
                asyncio.create_task(self._handle_ai_clue(on_turn))
