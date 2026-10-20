"""Synchronous game state and rules: no sockets, tasks, or AI clients."""

import pathlib
import random
import uuid
from typing import Optional

from codenames.model import Role, Tile, User


def generate_tiles() -> list[Tile]:
    words = (pathlib.Path(__file__).parent.parent.parent / "wordlist.txt").read_text().splitlines()
    teams = ["red"] * 9 + ["blue"] * 8 + ["assassin"] + ["neutral"] * 7
    tiles = [Tile(word.strip(), team) for word, team in zip(random.sample(words, 25), teams)]
    random.shuffle(tiles)
    return tiles


class CodenamesGame:
    def __init__(self, users: list[User]):
        self.users = list(users)
        self.tiles = generate_tiles()
        self.id = str(uuid.uuid4())
        self.current_turn = Role.RED_SPYMASTER
        self.turn_id = 0
        self.revision = 0
        self.clue: Optional[tuple[str, int]] = None
        self.guesses_remaining = 0
        self.winner: Optional[str] = None

    def check_win(self) -> Optional[str]:
        if self.winner:
            return self.winner
        for team in ("red", "blue"):
            if not any(tile.team == team and not tile.revealed for tile in self.tiles):
                return team
        if any(tile.team == "assassin" and tile.revealed for tile in self.tiles):
            return self.current_turn.team
        return None

    def is_user_turn(self, user: User) -> bool:
        return user in self.users and user.role == self.current_turn

    def get_on_turn_user(self) -> User:
        return next(user for user in self.users if self.is_user_turn(user))

    def set_turn(self, role: Role) -> None:
        self.current_turn = role
        self.turn_id += 1

    def provide_clue(self, user: User, word: str, number: int) -> bool:
        if self.check_win():
            return False
        if not self.is_user_turn(user) or not user.is_spy_master:
            raise ValueError("It is not your spymaster turn")
        if not isinstance(word, str) or not word.strip():
            raise ValueError("Clue word must be a nonempty string")
        if type(number) is not int or not 1 <= number <= sum(not tile.revealed for tile in self.tiles):
            raise ValueError("Clue count must be a positive integer within the unrevealed board")
        self.clue = (word.strip(), number)
        self.guesses_remaining = number
        self.set_turn(Role.from_team_and_role(user.team, False))
        self.revision += 1
        return True

    def guess_tile(self, user: User, tile: Tile) -> bool:
        if self.check_win():
            return False
        if not self.is_user_turn(user) or user.is_spy_master:
            raise ValueError("It is not your operative turn")
        if tile not in self.tiles:
            raise ValueError("Tile is not on this board")
        if tile.revealed or self.guesses_remaining <= 0:
            return False
        tile.reveal()
        self.guesses_remaining = self.guesses_remaining - 1 if tile.team == user.team else 0
        if self.guesses_remaining <= 0:
            self._end_turn(user)
        self.revision += 1
        self.winner = self.check_win()
        return True

    def _end_turn(self, user: User) -> None:
        self.guesses_remaining = 0
        self.clue = None
        self.set_turn(Role.from_team_and_role("red" if user.team == "blue" else "blue", True))

    def pass_turn(self, user: User) -> bool:
        if self.check_win():
            return False
        if not self.is_user_turn(user) or user.is_spy_master:
            raise ValueError("It is not your operative turn")
        self._end_turn(user)
        self.revision += 1
        return True

    def remove_user(self, user: User, replacement: Optional[User] = None) -> bool:
        if user not in self.users:
            return False
        on_turn = self.is_user_turn(user)
        self.users.remove(user)
        if replacement is not None:
            self.users.append(replacement)
            if on_turn:
                self.set_turn(self.current_turn)
        self.revision += 1
        return on_turn
