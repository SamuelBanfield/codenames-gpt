
import asyncio
import pathlib
import random
from typing import List, Literal, Optional, Tuple

from typing import TYPE_CHECKING
from codenames.services.clue_service import ClueService
from codenames.options import GUESS_DELAY
from codenames.model import Role, Tile, User
from codenames.gpt.gpt_agent import GPTAgent

def generate_tiles() -> List[Tile]:
    with open(pathlib.Path(__file__).parent.parent.parent / "wordlist.txt") as f:
        words = f.readlines()
    used_words = random.sample(words, 25)
    teams = ["red"] * 9 + ["blue"] * 8 + ["assassin"] + ["neutral"] * 7
    all_tiles = [Tile(word.strip(), team) for word, team in zip(used_words, teams)]
    random.shuffle(all_tiles)
    return all_tiles


class CodenamesGame:
    def __init__(self, users: List[User]):
        self.users = users
        self.tiles = generate_tiles()
        self.current_turn: Role = Role.RED_SPYMASTER
        self.guesses_remaining = 0
        self.clue: Optional[Tuple[str, int]] = None
        # Allow dependency injection of clue service (for testing / alternate AI implementations)
        self.clue_service: ClueService = ClueService(GPTAgent())

    async def broadcast_state_update(self, is_on_turn_update: bool):
        await asyncio.gather(*(user.send(self.get_state_update(user, is_on_turn_update)) for user in self.users))

    def get_state_update(self, user: User, is_on_turn_update: bool) -> dict:
        return {
            "serverMessageType": "stateUpdate",
            "tiles": [tile.to_json(user.is_spy_master) for tile in self.tiles],
            "players": [u.to_json() for u in self.users],
            "onTurnRole": self.current_turn.index,
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

    async def guess_tile(self, user: User, tile: Tile) -> None:
        if self.check_win():
            print("Ignoring guess as game is over")
            return
        if self.is_user_turn(user) and not user.is_spy_master:
            tile.reveal()
            may_continue: bool = self.update_guesses_remaining(tile, user)
            await self.broadcast_state_update(self.guesses_remaining <= 0)
            on_turn = self.get_on_turn_user()
            if not may_continue and not on_turn.is_human:
                asyncio.create_task(self.clue_service.create_clue(self, on_turn))
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
            assert user.team is not None, "User team should be set"
            other_team = "red" if user.team == "blue" else "blue"
            self.current_turn = Role.from_team_and_role(other_team, True)
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
            assert user.team is not None, "User team should be set"
            self.current_turn = Role.from_team_and_role(user.team, False)
            await self.broadcast_state_update(True)
            on_turn_user = self.get_on_turn_user()
            if not on_turn_user.is_human:
                asyncio.create_task(self.clue_service.make_guesses(word, number, self, on_turn_user))
        else:
            print(f"Ignoring clue from {user.name} as it is not their turn")

    async def pass_turn(self, user: User):
        if self.is_user_turn(user) and not user.is_spy_master:
            self.guesses_remaining = 0
            assert user.team is not None, "User team should be set"
            other_team = "red" if user.team == "blue" else "blue"
            self.current_turn = Role.from_team_and_role(other_team, True)
            self.clue = None
            await self.broadcast_state_update(True)
            on_turn = self.get_on_turn_user()
            if not on_turn.is_human:
                asyncio.create_task(self.clue_service.create_clue(self, on_turn))
