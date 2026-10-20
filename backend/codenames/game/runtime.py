"""Own a game's asynchronous effects; all rule mutations go through its state."""

import asyncio
import logging
from typing import Callable, Optional

from codenames.game.factory import create_ai_user
from codenames.game.game import CodenamesGame
from codenames.gpt.chat_gpt import ChatGPT
from codenames.model import Tile, User
from codenames.options import GUESS_DELAY
from codenames.services.connection_service import ConnectionManager
from codenames.util import get_tile_by_word

logger = logging.getLogger(__name__)


class GameRuntime:
    def __init__(self, state: CodenamesGame, connections: ConnectionManager,
                 ai_factory: Callable[[], ChatGPT] = ChatGPT, guess_delay: float = GUESS_DELAY):
        self.state = state
        self.connections = connections
        self.lobby_id: Optional[str] = None
        self.started = True
        self.disposed = False
        self.ai_error: Optional[str] = None
        self.guess_delay = guess_delay
        self._ai_factory = ai_factory
        self._ai: Optional[ChatGPT] = None
        self._tasks: set[asyncio.Task] = set()
        self._ai_turns: dict[int, asyncio.Task] = {}

    @property
    def ai(self) -> ChatGPT:
        if self._ai is None:
            if self.disposed or self.state.check_win():
                raise ValueError("Game is no longer active")
            self._ai = self._ai_factory()
        return self._ai

    def get_state_update(self, user: User, is_on_turn_update: bool) -> dict:
        game = self.state
        winner = game.check_win()
        return {
            "serverMessageType": "stateUpdate",
            "tiles": [tile.to_json(user.is_spy_master) for tile in game.tiles],
            "players": [other.to_json(in_lobby=other.is_human, in_game=True) for other in game.users],
            "onTurnRole": game.current_turn.index,
            "guessesRemaining": game.guesses_remaining,
            "clue": {"word": game.clue[0].upper(), "number": game.clue[1]} if game.clue else None,
            "new_turn": is_on_turn_update,
            "winner": winner,
            "gameId": game.id,
            "lobbyId": self.lobby_id,
            "turnId": game.turn_id,
            "revision": game.revision,
            "phase": "finished" if winner else "active" if self.started else "starting",
            "aiError": self.ai_error,
        }

    async def broadcast_state_update(self, is_on_turn_update: bool):
        if not self.disposed:
            await self.connections.broadcast(
                self.state.users, lambda user: self.get_state_update(user, is_on_turn_update),
            )

    def is_current_turn(self, user: User, turn: int) -> bool:
        return (not self.disposed and self.started and not self.state.check_win()
                and self.state.turn_id == turn and self.state.is_user_turn(user))

    def validate_action(self, data: dict) -> None:
        if not self.started or self.disposed:
            raise ValueError("Game is not ready for actions")
        if data.get("gameId") is not None and data["gameId"] != self.state.id:
            raise ValueError("Action belongs to a different game")
        if data.get("turnId") is not None and (type(data["turnId"]) is not int or data["turnId"] != self.state.turn_id):
            raise ValueError("Action belongs to an earlier turn")

    def _cancel_tasks(self):
        current = asyncio.current_task()
        for task in self._tasks:
            if task is not current and not task.done():
                task.cancel()

    async def _after_change(self, old_turn: int):
        turn = self.state.turn_id
        changed_turn = old_turn != turn
        if changed_turn or self.state.check_win():
            self.ai_error = None
            self._cancel_tasks()
        await self.broadcast_state_update(changed_turn)
        if self.state.check_win():
            await self._close_ai()
        elif changed_turn:
            self.schedule_ai_turn(turn)

    async def provide_clue(self, user: User, word: str, number: int):
        if self.disposed or not self.started:
            return False
        turn = self.state.turn_id
        if self.state.provide_clue(user, word, number):
            await self._after_change(turn)
            return True
        return False

    async def guess_tile(self, user: User, tile: Tile):
        if self.disposed or not self.started:
            return False
        turn = self.state.turn_id
        if self.state.guess_tile(user, tile):
            await self._after_change(turn)
            return True
        return False

    async def guess_word(self, user: User, word: str):
        if self.state.check_win():
            return self.get_state_update(user, False)
        tile = get_tile_by_word(word, self.state.tiles)
        if not await self.guess_tile(user, tile):
            return self.get_state_update(user, False)

    async def pass_turn(self, user: User):
        if self.disposed or not self.started:
            return
        turn = self.state.turn_id
        if self.state.pass_turn(user):
            await self._after_change(turn)

    def schedule_ai_turn(self, expected_turn: Optional[int] = None):
        turn = self.state.turn_id
        if self.disposed or not self.started or self.state.check_win() or (expected_turn is not None and expected_turn != turn):
            return
        user = self.state.get_on_turn_user()
        if user.is_human or (turn in self._ai_turns and not self._ai_turns[turn].done()):
            return
        task = asyncio.create_task(self.create_clue(user) if user.is_spy_master else self.make_guesses(user))
        self._tasks.add(task)
        self._ai_turns[turn] = task

        def finished(completed):
            self._tasks.discard(completed)
            if self._ai_turns.get(turn) is completed:
                self._ai_turns.pop(turn, None)
            if not completed.cancelled() and completed.exception():
                logger.error("AI task failed: %s", completed.exception())

        task.add_done_callback(finished)

    async def create_clue(self, user: User):
        turn = self.state.turn_id
        if not self.is_current_turn(user, turn) or not user.is_spy_master:
            return
        try:
            word, number = await self.ai.provide_clue(user, self.state.tiles)
            if self.is_current_turn(user, turn):
                await self.provide_clue(user, word, number)
        except Exception:
            logger.exception("AI clue generation failed")
            if self.is_current_turn(user, turn):
                await self.report_ai_error("AI clue generation failed. You can retry the AI turn.")

    async def make_guesses(self, user: User):
        turn = self.state.turn_id
        if not self.is_current_turn(user, turn) or user.is_spy_master or not self.state.clue:
            return
        try:
            guesses = await self.ai.make_guesses(*self.state.clue, self.state.tiles)
            for word in guesses:
                if not self.is_current_turn(user, turn) or self.state.guesses_remaining <= 0:
                    return
                await asyncio.sleep(self.guess_delay)
                if not self.is_current_turn(user, turn):
                    return
                try:
                    tile = get_tile_by_word(word, self.state.tiles)
                except ValueError:
                    continue
                if not tile.revealed:
                    await self.guess_tile(user, tile)
            if self.is_current_turn(user, turn):
                await self.pass_turn(user)
        except Exception:
            logger.exception("AI guessing failed")
            if self.is_current_turn(user, turn):
                await self.report_ai_error("AI guessing failed; its turn has been passed.")
                if self.is_current_turn(user, turn):
                    await self.pass_turn(user)

    async def report_ai_error(self, message: str):
        if self.disposed or self.state.check_win():
            return
        self.ai_error = message
        self.state.revision += 1
        await self.connections.broadcast(self.state.users, lambda user: {
            "serverMessageType": "error", "message": message, "code": "aiUnavailable",
            "lobbyId": self.lobby_id, "gameId": self.state.id,
        })
        await self.broadcast_state_update(False)

    async def retry_ai_turn(self):
        if self.disposed or self.state.check_win() or not self.ai_error or self.state.get_on_turn_user().is_human:
            raise ValueError("There is no failed AI turn to retry")
        turn = self.state.turn_id
        self._cancel_tasks()
        await asyncio.gather(*list(self._tasks), return_exceptions=True)
        if self.disposed or self.state.check_win() or self.state.turn_id != turn:
            return
        self.ai_error = None
        self.state.revision += 1
        await self.broadcast_state_update(False)
        self.schedule_ai_turn(turn)

    def remove_user(self, user: User, replace_with_ai: bool) -> bool:
        replacement = (create_ai_user(user.role)
                       if replace_with_ai and user.role and not self.state.check_win() else None)
        on_turn = self.state.remove_user(user, replacement)
        if on_turn:
            self._cancel_tasks()
            self.ai_error = None
        return on_turn

    async def _close_ai(self):
        client, self._ai = self._ai, None
        if client is not None:
            try:
                await client.close()
            except Exception:
                logger.exception("Failed to close AI client")

    async def dispose(self):
        self.disposed = True
        self._cancel_tasks()
        await asyncio.gather(*(task for task in self._tasks if task is not asyncio.current_task()),
                             return_exceptions=True)
        await self._close_ai()
