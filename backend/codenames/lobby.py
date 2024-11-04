from typing import List, Optional, Dict, Any
import uuid
from codenames.game import CodenamesGame
from codenames.gpt.agent import GPTConnection
from codenames.model import CodenamesConnection, User

ROLES = [("red", True), ("blue", True), ("red", False), ("blue", False)]

class Lobby:
    def __init__(self) -> None:
        self.users: List[User] = []
        self.game: Optional[CodenamesGame] = None
        self.id: uuid.UUID = uuid.uuid4()

    def add_user(self, user: User) -> None:
        self.users.append(user)
        user.in_lobby = True

    def remove_user(self, user: User) -> None:
        self.users.remove(user)
        if not self.users:
            self.game = None

    def all_ready(self) -> bool:
        return all(user.is_ready for user in self.users if user.name)

    async def send_all(self, message: Dict[str, Any]) -> None:
        print(f"Sending message to all: {message['serverMessageType']}")
        for user in self.users:
            await user.connection.send(message)

    async def request(self, user: User, message: Dict[str, Any]) -> None:
        if self.game:
            await self.game.handle_request(user, message)
        else:
            await self.lobby_request(user, message)

    def get_role_assignments(self) -> Dict[int, str]:
        role_assignments = {}
        for user in self.users:
            if user.team:
                role_assignments[ROLES.index((user.team, user.is_spy_master))] = user.name
        return role_assignments

    async def lobby_request(self, user: CodenamesConnection, message: Dict[str, Any]) -> None:
        if message.get("clientMessageType") == "preferencesRequest":
            self.update_user_preferences(user, message.get("player", {}))
            if self.all_ready():
                await self.start_game()
            else:
                await self.send_player_update()
        else:
            print(f"Unhandled message in lobby: {message}")

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
            clue, number = self.game.gpt.provide_clue(on_turn, self.game.tiles)
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