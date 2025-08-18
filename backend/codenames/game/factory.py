from typing import Dict, List

from codenames.gpt.chat_gpt import GPTConnection
from codenames.model import Role, User
from codenames.game.game import CodenamesGame


class GameFactory:

    @staticmethod
    def create_game(users: List[User], role_assignments: Dict[int, str]) -> 'CodenamesGame':
        """Create a new Codenames game instance with the given users, creating AI players if needed."""
        gpt_players = GameFactory.create_gpt_players(role_assignments)
        game = CodenamesGame(users + gpt_players)
        for user in game.users:
            user.in_game = True
        return game
    
    @staticmethod
    def create_gpt_players(role_assignments: Dict[int, str]) -> List[User]:
        gpt_players = []
        for role in Role.all_roles():
            index = role.index
            team, is_spy_master = role.team, role.is_spymaster
            if index not in role_assignments:
                gpt_connection = GPTConnection()
                gpt_player = User(gpt_connection, False)
                gpt_player.is_spy_master = is_spy_master
                gpt_player.team = team
                gpt_player.name = f"{'GPT Spy Master' if is_spy_master else 'GPT Guesser'} ({team})"
                gpt_player.is_ready = True
                gpt_players.append(gpt_player)
        return gpt_players
