from typing import List, Tuple
from codenames.gpt.agent import ChatGPT
from codenames.model import CodenamesConnection, Tile, User
from codenames.options import GUESS_DELAY

class GPTConnection(CodenamesConnection):

    def __init__(self):
        super().__init__()

    async def send(self, message: dict):
        '''No op for AI'''
        return

class GPTAgent:
    def __init__(self):
        self.chat_gpt: ChatGPT = ChatGPT()

    async def provide_clue(self, user: User, tiles: List[Tile]) -> Tuple[str, int]:
        clue_word, clue_number = await self.chat_gpt.get_clue(
            [tile.word for tile in tiles if tile.team == user.team and not tile.revealed],
            [tile.word for tile in tiles if tile.team != user.team and not tile.revealed]
        )
        return (clue_word, clue_number)

    async def make_guesses(self, word: str, number: int, tiles: List[Tile]) -> List[str]:
        guess_words = await self.chat_gpt.guess((word, number), [tile.word for tile in tiles if not tile.revealed])

        return guess_words

