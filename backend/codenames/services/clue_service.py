
import asyncio
from codenames.util import get_tile_by_word
from codenames.options import GUESS_DELAY
from codenames.model import Tile, User
from codenames.gpt.gpt_agent import GPTAgent


class ClueService:
    def __init__(self, gpt_agent: GPTAgent):
        self.gpt_agent = gpt_agent

    async def create_clue(self, game, user: User):
        """Handle AI clue generation asynchronously to avoid blocking human input"""
        try:
            clue, number = await self.gpt_agent.provide_clue(user, game.tiles)
            # await asyncio.sleep(GUESS_DELAY)
            await game.provide_clue(user, clue, number)
        except Exception as e:
            print(f"Error in AI clue generation for {user.name}: {e}")

    async def make_guesses(self, word: str, number: int, game, user: User):
        """Handle AI guessing asynchronously to avoid blocking human input"""
        try:
            guesses = await self.gpt_agent.make_guesses(word, number, game.tiles)
            if not guesses:
                await game.pass_turn(user)
                return

            while game.guesses_remaining > 0 and guesses:
                await asyncio.sleep(GUESS_DELAY)
                guess_word = guesses.pop(0)
                try:
                    tile = get_tile_by_word(guess_word, game.tiles)
                    await game.guess_tile(user, tile)
                except ValueError:
                    print(f"AI {user.name} guessed invalid word: {guess_word}")
                    # Skip this invalid guess and continue with the next one
                    continue
        except Exception as e:
            print(f"Error in AI guessing for {user.name}: {e}")