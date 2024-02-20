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
                        index = int(player_data["role"])
                        assigned_roles = self.get_role_assignments()
                        if index not in assigned_roles:
                            user.team, user.is_spy_master = ROLES[index]
                if self.all_ready():
                    
                    gpt_players = [] # Players controlled by chat gpt
                    role_assignements = self.get_role_assignments()
                    agent = GPTAgent()
                    for index, (team, is_spy_master) in enumerate(ROLES):
                        if not index in role_assignements:
                            gpt_connection = GPTConnection(agent)
                            gpt_player = User(gpt_connection)
                            gpt_player.is_spy_master = is_spy_master
                            gpt_player.team = team
                            gpt_player.name = f"{"GPT Spy Master" if is_spy_master else "GPT Guesser"} ({team})"
                            gpt_player.is_ready = True
                            gpt_players.append(gpt_player)

                    self.game = CodenamesGame(self.users + gpt_players)
                    for user in gpt_players:
                        user.connection.set_end_point(self.game)
                    for user in self.users:
                        user.in_game = True
                    await self.send_all({
                        "serverMessageType": "playerUpdate",
                        "players": [user.__json__() for user in self.users]
                    })
                    await self.game._broadcast_state_update(True)
                else:
                    await self.send_all({
                        "serverMessageType": "playerUpdate",
                        "players": [user.__json__() for user in self.users]
                    })
            