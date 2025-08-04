from typing import List, Optional, Dict, Any
import uuid
from codenames.game import CodenamesGame
from codenames.gpt.agent import GPTConnection
from codenames.model import CodenamesConnection, User

ROLES = [("red", True), ("blue", True), ("red", False), ("blue", False)]

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

    def all_ready(self) -> bool:
        return all(user.is_ready for user in self.users if user.name)

    async def send_all(self, message: Dict[str, Any]) -> None:
        print(f"Sending message to all: {message['serverMessageType']}")
        for user in self.users:
            await user.connection.send(message)

    def get_role_assignments(self) -> Dict[int, str]:
        role_assignments = {}
        for user in self.users:
            if user.team:
                role_assignments[ROLES.index((user.team, user.is_spy_master))] = user.name
        return role_assignments

    def update_user_preferences(self, user: User, player_data: Dict) -> None:
        user.name = player_data.get("name", user.name)
        user.is_ready = player_data.get("ready", user.is_ready)
        if "role" in player_data and player_data["role"] is not None:
            index = int(player_data["role"])
            assigned_roles = self.get_role_assignments()
            if index not in assigned_roles:
                user.team, user.is_spy_master = ROLES[index]

    async def start_game(self) -> None:
        gpt_players = self.create_gpt_players()
        self.game = CodenamesGame(self.users + gpt_players)
        self.mark_users_in_game()
        await self.send_player_update()
        await self.game.broadcast_state_update(True)
        on_turn = self.game.get_on_turn_user()
        if not on_turn.is_human:
            clue, number = await self.game.gpt.provide_clue(on_turn, self.game.tiles)
            await self.game.provide_clue(on_turn, clue, number)

    def create_gpt_players(self) -> List[User]:
        gpt_players = []
        role_assignments = self.get_role_assignments()
        for index, (team, is_spy_master) in enumerate(ROLES):
            if index not in role_assignments:
                gpt_connection = GPTConnection()
                gpt_player = User(gpt_connection, False)
                gpt_player.is_spy_master = is_spy_master
                gpt_player.team = team
                gpt_player.name = f"{'GPT Spy Master' if is_spy_master else 'GPT Guesser'} ({team})"
                gpt_player.is_ready = True
                gpt_players.append(gpt_player)
        return gpt_players

    def mark_users_in_game(self) -> None:
        for user in self.users:
            user.in_game = True

    async def send_player_update(self) -> None:
        await self.send_all({
            "serverMessageType": "playerUpdate",
            "players": [user.to_json() for user in self.users]
        })