"""Explicit transport/runtime fixtures shared by the regression suites."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

from codenames.game.factory import GameFactory
from codenames.game.runtime import GameRuntime
from codenames.model import User
from codenames.services.connection_service import Connection, ConnectionManager
from codenames.services.lobby_service import InMemoryLobbyRepository, LobbyService


connections = None


def reset_connections():
    global connections
    connections = ConnectionManager()


def ai_factory():
    return Mock(return_value=SimpleNamespace(
        provide_clue=AsyncMock(return_value=("CLUE", 1)),
        make_guesses=AsyncMock(return_value=[]), close=AsyncMock(),
    ))


def make_user(name="Player", role=None, is_human=True):
    user = User(is_human=is_human, role=role)
    user.name = name
    if is_human:
        connection = Mock(spec=Connection)
        connection.id = user.id
        connection.send = AsyncMock()
        connections.add_session(user, connection)
    return user


def context_for(user, lobby=None):
    # Membership is set by the room coordinator, never by this fixture.
    return connections.get_session(user.id)


def connection_for(user):
    return context_for(user).connection


def make_runtime(users):
    return GameRuntime(GameFactory.create_game(users), connections, ai_factory(), guess_delay=0)


def make_service():
    return LobbyService(InMemoryLobbyRepository(), connections, ai_factory(), guess_delay=0)
