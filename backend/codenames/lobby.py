import json
from typing import List, Optional

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
        return all(user.is_ready for user in self.users)
    
    async def send_all(self, message):
        print(f"Sending message to all: {message["serverMessageType"]}")
        for user in self.users:
            await user.connection.send(json.dumps(message))
    
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
                    self.game = CodenamesGame(self.users)
                    for user in self.users:
                        user.in_game = True
                await self.send_all({
                    "serverMessageType": "playerUpdate",
                    "players": [user.__json__() for user in self.users]
                })
            