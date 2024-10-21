import time
from codenames.gpt.agent import GPTAgent
from codenames.model import Role, CodenamesConnection, CodenamesGame
from codenames.options import GUESS_DELAY

class GPTConnection(CodenamesConnection):

    def __init__(self, agent: GPTAgent):
        super().__init__()
        self.agent = agent  # GPT to provide clues/guesses
        self.end_point: CodenamesGame = None
        self.user = None

    def set_end_point(self, end_point: CodenamesGame):
        self.end_point = end_point  # Where the connection can send its clues/guesses
        self.user = end_point.get_user_by_connection(self)

    async def send(self, message: dict):
        if message["serverMessageType"] == "stateUpdate":
            if message["new_turn"] and message["winner"] is None:
                role = [role.value for role in Role][message["onTurnRole"]]
                if role[0] == self.user.team and role[1] == self.user.is_spy_master:
                    if self.user.is_spy_master:
                        await self._provide_clue()
                    else:
                        await self._make_guesses()

    async def _provide_clue(self):
        print("GPT is providing clue")
        clue_word, clue_number = self.agent.get_clue(
            [tile.word for tile in self.end_point.tiles if tile.team == self.user.team and not tile.revealed],
            [tile.word for tile in self.end_point.tiles if tile.team != self.user.team and not tile.revealed]
        )
        await self.end_point.provide_clue(self.user, clue_word, clue_number)

    async def _make_guesses(self):
        print("GPT is guessing")
        guess_words = self.agent.guess(self.end_point.clue, [tile.word for tile in self.end_point.tiles if not tile.revealed])
        for word in guess_words:
            # Insert some delay, otherwise it's too fast to see what's happening
            time.sleep(int(GUESS_DELAY))
            await self.end_point.handle_request(
                self.user,
                {
                    "clientMessageType": "guessTile",
                    "word": word.split(",")[0]
                }
            )
        if self.end_point.guesses_remaining > 0:
            await self.end_point.pass_turn(self.user)
