"""Explicit transport/runtime fixtures shared by the regression suites."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

from codenames.game.factory import create_game
from codenames.game.runtime import GameRuntime
from codenames.model import User
from codenames.connections import Connection, Connections
from codenames.rooms import Rooms


connections = None


def reset_connections():
    global connections
    connections = Connections()


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
        connection.send = AsyncMock()
        connections.add_session(user, connection)
    return user


def context_for(user, lobby=None):
    # Membership is set by the room coordinator, never by this fixture.
    return connections.get_session(user.id)


def connection_for(user):
    return context_for(user).connection


async def make_runtime(users):
    runtime = GameRuntime(create_game(users), connections, ai_factory(), guess_delay=0)
    await runtime.activate()
    return runtime


def make_service():
    return Rooms(connections, ai_factory(), guess_delay=0)
