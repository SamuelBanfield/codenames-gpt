from codenames.game.game import CodenamesGame
from codenames.model import Role, User


def create_ai_user(role: Role) -> User:
    user = User(is_human=False, role=role)
    user.name = f"GPT {'Spy Master' if role.is_spymaster else 'Guesser'} ({role.team})"
    user.is_ready = True
    return user


def create_game(users: list[User]) -> CodenamesGame:
    occupied = {user.role for user in users}
    return CodenamesGame(list(users) + [create_ai_user(role) for role in Role if role not in occupied])
