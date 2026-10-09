import logging
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
        self.revision = 0
        self.game: Optional[CodenamesGame] = None
        self.id: uuid.UUID = uuid.uuid4()
        self.add_user(user)

    def add_user(self, user: User) -> None:
        if user not in self.users:
            self.users.append(user)
            self.revision += 1
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
        for user in list(self.users):
            if user not in self.users:
                continue
            try:
                await user.connection.send(message)
            except Exception as error:
                logging.warning("Lobby broadcast recipient failed: %s", error)

    def get_role_assignments(self) -> Dict[int, str]:
        role_assignments = {}
        for user in self.users:
            if user.team:
                role = Role.from_team_and_role(user.team, user.is_spy_master)
                role_assignments[role.index] = user.name
        return role_assignments

    def ready_to_start(self) -> bool:
        return self.game is None and bool(self.users) and all(
            user.name and user.team is not None and user.is_ready for user in self.users
        )

    async def start_game(self) -> None:
        if self.game is not None:
            return
        self.game = GameFactory.create_game(self.users, self.get_role_assignments())
        self.revision += 1
        game = self.game
        game.lobby_id = str(self.id)
        game.started = False
        await self.send_player_update()
        if game.disposed:
            return
        game.started = True
        game.revision += 1
        turn = game.turn_id
        await game.broadcast_state_update(True)
        game.schedule_ai_turn(turn)

    async def send_player_update(self) -> None:
        await self.send_all(self.get_player_update())

    def get_player_update(self) -> Dict[str, Any]:
        return {
            "serverMessageType": "playerUpdate",
            "players": [user.to_json() for user in self.users],
            "lobbyId": str(self.id),
            "lobbyRevision": self.revision,
        }
