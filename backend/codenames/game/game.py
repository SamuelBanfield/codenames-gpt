
import asyncio
import logging
import pathlib
import random
import uuid
from typing import List, Literal, Optional, Tuple

from codenames.services.clue_service import ClueService
from codenames.model import Role, Tile, User
from codenames.gpt.gpt_agent import GPTAgent
from codenames.gpt.chat_gpt import GPTConnection

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
        self.id = str(uuid.uuid4())
        self.lobby_id: Optional[str] = None
        self.turn_id = 0
        self.revision = 0
        self.started = True
        self.disposed = False
        self.winner: Optional[Literal["red", "blue"]] = None
        self.ai_error: Optional[str] = None
        self._tasks: set[asyncio.Task] = set()
        self._ai_turns: dict[int, asyncio.Task] = {}

    async def broadcast_state_update(self, is_on_turn_update: bool):
        if self.disposed:
            return
        results = await asyncio.gather(
            *(user.send(self.get_state_update(user, is_on_turn_update)) for user in self.users),
            return_exceptions=True,
        )
        for result in results:
            if isinstance(result, Exception):
                logging.warning("Game broadcast recipient failed: %s", result)

    def get_state_update(self, user: User, is_on_turn_update: bool) -> dict:
        return {
            "serverMessageType": "stateUpdate",
            "tiles": [tile.to_json(user.is_spy_master) for tile in self.tiles],
            "players": [u.to_json() for u in self.users],
            "onTurnRole": self.current_turn.index,
            "guessesRemaining": self.guesses_remaining,
            "clue": {"word": self.clue[0].upper(), "number": self.clue[1]} if self.clue else None,
            "new_turn": is_on_turn_update,
            "winner": self.check_win(),
            "gameId": self.id,
            "lobbyId": self.lobby_id,
            "turnId": self.turn_id,
            "revision": self.revision,
            "phase": "finished" if self.check_win() else "active" if self.started else "starting",
            "aiError": self.ai_error,
        }

    def check_win(self) -> Optional[Literal["red", "blue"]]:
        if self.winner:
            return self.winner
        if not any(tile.team == "red" and not tile.revealed for tile in self.tiles):
            return "red"
        if not any(tile.team == "blue" and not tile.revealed for tile in self.tiles):
            return "blue"
        if any(tile.team == "assassin" and tile.revealed for tile in self.tiles):
            return self.current_turn.value[0]
        return None

    async def guess_tile(self, user: User, tile: Tile) -> None:
        if self.disposed or self.check_win():
            print("Ignoring guess as game is over")
            return
        if self.started and self.is_user_turn(user) and not user.is_spy_master:
            if tile not in self.tiles or tile.revealed or self.guesses_remaining <= 0:
                return
            tile.reveal()
            may_continue = self.update_guesses_remaining(tile, user)
            self.revision += 1
            self._finish_if_needed()
            turn = self.turn_id
            await self.broadcast_state_update(not may_continue)
            if self.winner:
                await self.clue_service.close()
            elif not may_continue:
                self.schedule_ai_turn(turn)
        else:
            print(f"Ignoring guess from {user.name} as it is not their turn")


    def is_user_turn(self, user: User) -> bool:
        return user in self.users and self.current_turn.value == (user.team, user.is_spy_master)

    def is_current_turn(self, user: User, turn: int) -> bool:
        return (not self.disposed and self.started and not self.check_win()
                and self.turn_id == turn and self.is_user_turn(user))

    def _cancel_tasks(self):
        current = asyncio.current_task()
        for task in self._tasks:
            if task is not current and not task.done():
                task.cancel()

    def _set_turn(self, role: Role):
        self.current_turn = role
        self.turn_id += 1
        self.ai_error = None
        self._cancel_tasks()

    def _finish_if_needed(self):
        winner = self.check_win()
        if winner:
            self.winner = winner
            self._cancel_tasks()

    def schedule_ai_turn(self, expected_turn: Optional[int] = None):
        turn = self.turn_id
        if self.disposed or not self.started or self.check_win() or (expected_turn is not None and expected_turn != turn):
            return
        user = self.get_on_turn_user()
        if user.is_human or (turn in self._ai_turns and not self._ai_turns[turn].done()):
            return

        async def play():
            if not self.is_current_turn(user, turn):
                return
            if user.is_spy_master:
                await self.clue_service.create_clue(self, user)
            elif self.clue:
                await self.clue_service.make_guesses(*self.clue, self, user)

        task = asyncio.create_task(play())
        self._tasks.add(task)
        self._ai_turns[turn] = task

        def finished(completed):
            self._tasks.discard(completed)
            if self._ai_turns.get(turn) is completed:
                self._ai_turns.pop(turn, None)
            if not completed.cancelled() and completed.exception():
                logging.error("AI task failed: %s", completed.exception())

        task.add_done_callback(finished)

    async def report_ai_error(self, message: str):
        if self.disposed or self.check_win():
            return
        self.ai_error = message
        self.revision += 1
        await asyncio.gather(*(user.send({
            "serverMessageType": "error", "message": message, "code": "aiUnavailable",
            "lobbyId": self.lobby_id, "gameId": self.id,
        }) for user in self.users if user.is_human), return_exceptions=True)
        await self.broadcast_state_update(False)

    async def dispose(self):
        self.disposed = True
        self._cancel_tasks()
        pending = [task for task in self._tasks if task is not asyncio.current_task()]
        await asyncio.gather(*pending, return_exceptions=True)
        await self.clue_service.close()

    async def retry_ai_turn(self):
        if self.disposed or self.check_win() or not self.ai_error or self.get_on_turn_user().is_human:
            raise ValueError("There is no failed AI turn to retry")
        turn = self.turn_id
        self._cancel_tasks()
        await asyncio.gather(*list(self._tasks), return_exceptions=True)
        if self.disposed or self.check_win() or self.turn_id != turn:
            return
        self.ai_error = None
        self.revision += 1
        await self.broadcast_state_update(False)
        self.schedule_ai_turn(turn)

    async def remove_user(self, user: User, replace_with_ai: bool):
        if user not in self.users:
            return
        on_turn = self.is_user_turn(user)
        self.users = [other for other in self.users if other is not user]
        if replace_with_ai and user.team and not self.check_win():
            replacement = User(GPTConnection(), False)
            replacement.team = user.team
            replacement.is_spy_master = user.is_spy_master
            replacement.is_ready = replacement.in_game = True
            replacement.name = f"GPT {'Spy Master' if user.is_spy_master else 'Guesser'} ({user.team})"
            self.users.append(replacement)
            if on_turn:
                self._set_turn(self.current_turn)
        self.revision += 1
        if replace_with_ai:
            await self.broadcast_state_update(False)
            if on_turn and not self.check_win():
                self.schedule_ai_turn()
    
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
            self._set_turn(Role.from_team_and_role(other_team, True))
            self.clue = None
            return False
        return True

    async def provide_clue(self, user: User, word: str, number: int):
        if self.disposed or self.check_win():
            print("Ignoring guess as game is over")
            return
        if self.started and self.is_user_turn(user) and user.is_spy_master:
            if not isinstance(word, str) or not word.strip():
                raise ValueError("Clue word must be a nonempty string")
            if type(number) is not int or not 1 <= number <= sum(not tile.revealed for tile in self.tiles):
                raise ValueError("Clue count must be a positive integer within the unrevealed board")
            self.clue = (word.strip(), number)
            self.guesses_remaining = number
            assert user.team is not None, "User team should be set"
            self._set_turn(Role.from_team_and_role(user.team, False))
            self.revision += 1
            turn = self.turn_id
            await self.broadcast_state_update(True)
            self.schedule_ai_turn(turn)
        else:
            print(f"Ignoring clue from {user.name} as it is not their turn")

    async def pass_turn(self, user: User):
        if self.disposed or self.check_win():
            return
        if self.started and self.is_user_turn(user) and not user.is_spy_master:
            self.guesses_remaining = 0
            assert user.team is not None, "User team should be set"
            other_team = "red" if user.team == "blue" else "blue"
            self._set_turn(Role.from_team_and_role(other_team, True))
            self.clue = None
            self.revision += 1
            turn = self.turn_id
            await self.broadcast_state_update(True)
            self.schedule_ai_turn(turn)
