import json
from typing import List, Optional
from codenames.gpt.agent import GPTAgent
from codenames.gpt.gpt_connection import GPTConnection

from codenames.model import CodenamesConnection, CodenamesGame, User

ROLES = [("red", True), ("blue", True), ("red", False), ("blue", False)]

class Lobby:

    def __init__(self) -> None:
        self.users: List[User] = []
        self.game: Optional[CodenamesGame] = None
    
    def add_user(self, user: User):
        self.users.append(user)

    def remove_user(self, user: User):
        self.users.remove(user)
        if not self.users:
            self.game = None

    def all_ready(self) -> bool:
        return all(user.is_ready for user in self.users if user.name != None and user.name != "")
    
    async def send_all(self, message):
        print(f"Sending message to all: {message["serverMessageType"]}")
        for user in self.users:
            await user.connection.send(message)

    async def request(self, user: User, message: json):
        if self.game:
            await self.game.request(user, message)
        else:
            await self.lobby_request(user, message)
    
    def get_role_assignments(self):
        role_assignments = {}
        for user in self.users:
            if user.team:
                role_assignments[ROLES.index((user.team, user.is_spy_master))] = user.name
        return role_assignments

    async def lobby_request(self, user: CodenamesConnection, message: json):
        if "clientMessageType" in message:
            if message["clientMessageType"] == "preferencesRequest":
                if "player" in message:
                    player_data = message["player"]
                    user.name = player_data["name"] if "name" in player_data else user.name
                    user.is_ready = player_data["ready"] if "ready" in player_data else user.is_ready
                    if "role" in player_data and player_data["role"] is not None:
                        user.team, user.is_spy_master = ROLES[int(player_data["role"])]
                if self.all_ready():
                    agent = GPTAgent()
                    
                    red_guesser_connection = GPTConnection(agent)
                    red_guesser = User(red_guesser_connection)
                    red_guesser.is_spy_master = False
                    red_guesser.team = "red"
                    red_guesser.name = "Red Guesser"
                    red_guesser.is_ready = True

                    blue_spy_master_connection = GPTConnection(agent)
                    blue_spy_master = User(blue_spy_master_connection)
                    blue_spy_master.is_spy_master = True
                    blue_spy_master.team = "blue"
                    blue_spy_master.name = "Blue Spy Master"
                    blue_spy_master.is_ready = True

                    blue_guesser_connection = GPTConnection(agent)
                    blue_guesser = User(blue_guesser_connection)
                    blue_guesser.is_spy_master = False
                    blue_guesser.team = "blue"
                    blue_guesser.name = "Blue Guesser"
                    blue_guesser.is_ready = True

                    self.game = CodenamesGame(self.users + [red_guesser, blue_spy_master, blue_guesser])
                    for user in [red_guesser, blue_spy_master, blue_guesser]:
                        user.connection.set_end_point(self.game)
                    for user in self.users:
                        user.in_game = True
                await self.send_all({
                    "serverMessageType": "playerUpdate",
                    "players": [user.__json__() for user in self.users]
                })
            