import asyncio
from typing import List, Optional, Dict, Any
import uuid
from codenames.game.factory import GameFactory
from codenames.game.game import CodenamesGame
from codenames.model import User, Role

class Lobby:
    def __init__(self, user: User, name: str) -> None:
        self.lobby_owner = user
        self.name = name
        self.users: List[User] = []
        self.game: Optional[CodenamesGame] = None
        self.id: uuid.UUID = uuid.uuid4()
        self.add_user(user)

    def add_user(self, user: User) -> None:
        self.users.append(user)
        user.in_lobby = True

    def to_json(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "id": str(self.id),
            "players": len(self.users),
            "game": self.game is not None
        }

    async def send_all(self, message: Dict[str, Any]) -> None:
        print(f"Sending message to all: {message['serverMessageType']}")
        for user in self.users:
            await user.connection.send(message)

    def get_role_assignments(self) -> Dict[int, str]:
        role_assignments = {}
        for user in self.users:
            if user.team:
                role = Role.from_team_and_role(user.team, user.is_spy_master)
                role_assignments[role.index] = user.name
        return role_assignments

    async def start_game(self) -> None:
        self.game = GameFactory.create_game(self.users, self.get_role_assignments())
        assert self.game is not None, "Game creation failed"
        await self.send_player_update()
        await self.game.broadcast_state_update(True)
        on_turn = self.game.get_on_turn_user()
        if not on_turn.is_human:
            asyncio.create_task(self.game.clue_service.create_clue(self.game, on_turn))

    async def send_player_update(self) -> None:
        await self.send_all({
            "serverMessageType": "playerUpdate",
            "players": [user.to_json() for user in self.users]
        })