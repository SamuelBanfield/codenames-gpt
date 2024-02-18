import asyncio
from codenames.gpt.agent import GPTAgent
from codenames.model import ROLES, CodenamesConnection, CodenamesGame


class GPTConnection(CodenamesConnection):

    def __init__(self, agent: GPTAgent):
        super().__init__()
        self.agent = agent # GPT to provide clues/guesses
        
    def set_end_point(self, end_point: CodenamesGame):
        self.end_point = end_point # Where the connection can send its clues/guesses
        self.user = end_point.get_user_by_connection(self)

    async def send(self, message):
        if message["serverMessageType"] == "stateUpdate" and message["new_turn"]:
            print(f"Handling turn update")
            role = ROLES[message["onTurnRole"]]
            if role[0] == self.user.team and role[1] == self.user.is_spy_master:
                if self.user.is_spy_master:
                    print("GPT is providing clue")
                    clue = self.agent.get_clue(
                        [tile.word for tile in self.end_point._tiles if tile.team == self.user.team],
                        [tile.word for tile in self.end_point._tiles if tile.team != self.user.team]
                    )
                    await self.end_point.provide_clue(self.user, clue[0], int(clue[1].strip()))
                else:
                    print("GPT is guessing")
                    guess = self.agent.guess(self.end_point.clue, [tile.word for tile in self.end_point._tiles if not tile.revealed])
                    await self.end_point.request(
                        self.user,
                        {
                            "clientMessageType": "guessTile",
                            "word": guess.split(",")[0]
                        }
                    )
