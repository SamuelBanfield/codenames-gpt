
import asyncio
import inspect
import logging
from codenames.util import get_tile_by_word
from codenames.options import GUESS_DELAY
from codenames.model import User
from codenames.gpt.gpt_agent import GPTAgent


class ClueService:
    def __init__(self, gpt_agent: GPTAgent):
        self.gpt_agent = gpt_agent
        self._closed = False

    async def create_clue(self, game, user: User):
        """Handle AI clue generation asynchronously to avoid blocking human input"""
        turn = game.turn_id
        if not game.is_current_turn(user, turn) or not user.is_spy_master:
            return
        try:
            clue, number = await self.gpt_agent.provide_clue(user, game.tiles)
            if game.is_current_turn(user, turn):
                await game.provide_clue(user, clue, number)
        except Exception as e:
            logging.exception("AI clue generation failed for %s", user.name)
            if game.is_current_turn(user, turn):
                await game.report_ai_error("AI clue generation failed. You can retry the AI turn.")

    async def make_guesses(self, word: str, number: int, game, user: User):
        """Handle AI guessing asynchronously to avoid blocking human input"""
        turn = game.turn_id
        if not game.is_current_turn(user, turn) or user.is_spy_master:
            return
        try:
            guesses = await self.gpt_agent.make_guesses(word, number, game.tiles)
            if not game.is_current_turn(user, turn):
                return
            guesses = list(guesses)
            while game.is_current_turn(user, turn) and game.guesses_remaining > 0 and guesses:
                await asyncio.sleep(GUESS_DELAY)
                if not game.is_current_turn(user, turn):
                    return
                guess_word = guesses.pop(0)
                try:
                    tile = get_tile_by_word(guess_word, game.tiles)
                    if not tile.revealed:
                        await game.guess_tile(user, tile)
                except ValueError:
                    print(f"AI {user.name} guessed invalid word: {guess_word}")
                    # Skip this invalid guess and continue with the next one
                    continue
            if game.is_current_turn(user, turn):
                await game.pass_turn(user)
        except Exception as e:
            logging.exception("AI guessing failed for %s", user.name)
            if game.is_current_turn(user, turn):
                await game.report_ai_error("AI guessing failed; its turn has been passed.")
                await game.pass_turn(user)

    async def close(self):
        if self._closed:
            return
        self._closed = True
        client = getattr(getattr(self.gpt_agent, "chat_gpt", None), "client", None)
        if client is not None:
            try:
                result = client.close()
                if inspect.isawaitable(result):
                    await result
            except Exception:
                logging.exception("Failed to close the AI client")
