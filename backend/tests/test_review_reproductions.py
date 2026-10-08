"""Regression specifications for findings 1-7 from the code review.

These tests intentionally assert the desired behavior, rather than accepting the
bugs as correct. They are expected to fail until the application is fixed.
"""

from unittest.mock import AsyncMock

import pytest

from codenames.game.factory import GameFactory
from codenames.game.game import CodenamesGame
from codenames.message_router.message_router import MessageRouter, UserContext
from codenames.model import CodenamesConnection, Role, Tile, User
from codenames.services.connection_service import ConnectionManager
from codenames.services.lobby_service import InMemoryLobbyRepository, LobbyService
from codenames.websocket_server import WebSocketServer


pytestmark = pytest.mark.reproduction


def make_user(name="Player", role=None):
    connection = CodenamesConnection()
    connection.send = AsyncMock()
    user = User(connection, True)
    user.name = name
    if role is not None:
        user.team = role.team
        user.is_spy_master = role.is_spymaster
    return user


@pytest.fixture
def game(monkeypatch):
    # Leave unrevealed words on both teams so a successful guess cannot end the game.
    def generate_tiles():
        return [
            Tile("APPLE", "red"),
            Tile("ORANGE", "red"),
            Tile("BERRY", "red"),
            Tile("OCEAN", "blue"),
            Tile("SKY", "blue"),
            Tile("DEATH", "assassin"),
        ]

    monkeypatch.setattr("codenames.game.game.generate_tiles", generate_tiles)
    monkeypatch.setattr("codenames.services.clue_service.GUESS_DELAY", 0)
    return CodenamesGame([make_user(role.name, role) for role in Role])


@pytest.fixture
def service():
    return LobbyService(InMemoryLobbyRepository())


def context_for(user, lobby):
    context = UserContext(user, str(user.connection.uuid))
    context.join_lobby(str(lobby.id))
    return context


@pytest.mark.parametrize(
    "guesses", [["APPLE"], ["APPLE", "NOT ON THE BOARD"]],
    ids=["short-response", "invalid-word-filtered"],
)
async def test_01_ai_passes_after_exhausting_a_short_guess_list(game, guesses):
    game.current_turn = Role.RED_OPERATIVE
    game.guesses_remaining = 3
    game.clue = ("FRUIT", 3)
    operative = game.get_on_turn_user()
    operative.is_human = False
    game.clue_service.gpt_agent.make_guesses = AsyncMock(return_value=list(guesses))

    await game.clue_service.make_guesses("FRUIT", 3, game, operative)

    assert game.tiles[0].revealed, "The valid AI guess should have been applied"
    assert game.current_turn == Role.BLUE_SPYMASTER, "An exhausted AI response must end its turn"
    assert game.guesses_remaining == 0
    assert game.clue is None


async def test_01_ai_guess_failure_does_not_leave_the_turn_stuck(game):
    game.current_turn = Role.RED_OPERATIVE
    game.guesses_remaining = 2
    game.clue = ("FRUIT", 2)
    operative = game.get_on_turn_user()
    operative.is_human = False
    game.clue_service.gpt_agent.make_guesses = AsyncMock(side_effect=RuntimeError("AI unavailable"))

    await game.clue_service.make_guesses("FRUIT", 2, game, operative)

    assert game.current_turn == Role.BLUE_SPYMASTER, "A failed AI guess request must recover the turn"
    assert game.guesses_remaining == 0


async def test_01_ai_clue_failure_notifies_humans_instead_of_only_printing(game):
    spymaster = game.get_on_turn_user()
    spymaster.is_human = False
    game.clue_service.gpt_agent.provide_clue = AsyncMock(side_effect=RuntimeError("AI unavailable"))

    await game.clue_service.create_clue(game, spymaster)

    delivered = [
        call.args[0]
        for user in game.users if user.is_human
        for call in user.connection.send.await_args_list
    ]
    assert any(message.get("serverMessageType") == "error" for message in delivered), (
        "Human players need an actionable notification when an AI clue request fails"
    )


async def test_02_disconnected_player_is_removed_from_game_roster(game, service):
    users = game.users
    lobby = await service.create_lobby(users[0], "Disconnect test")
    for user in users[1:]:
        await service.join_lobby(user, str(lobby.id))
    # Use the real factory: it copies the human roster into a separate game list.
    lobby.game = GameFactory.create_game(lobby.users, lobby.get_role_assignments())
    server = WebSocketServer(service, ConnectionManager())

    await server._cleanup_connection(context_for(users[0], lobby))

    assert users[0] not in lobby.users
    assert users[0] not in lobby.game.users, "Cleanup must update the active game, too"


async def test_02_broadcast_after_disconnect_reaches_remaining_players(game, service):
    departed = game.users[0]
    lobby = await service.create_lobby(departed, "Broadcast test")
    for user in game.users[1:]:
        await service.join_lobby(user, str(lobby.id))
    lobby.game = GameFactory.create_game(lobby.users, lobby.get_role_assignments())
    await service.leave_lobby(departed, str(lobby.id))
    departed.connection.send.side_effect = ConnectionError("socket is closed")
    remaining = lobby.users[0]

    await lobby.game.broadcast_state_update(False)

    remaining.connection.send.assert_awaited()
    departed.connection.send.assert_not_awaited()


async def test_02_lobby_departure_broadcasts_the_updated_roster(service):
    departed = make_user("Departed", Role.RED_SPYMASTER)
    remaining = make_user("Remaining", Role.BLUE_SPYMASTER)
    lobby = await service.create_lobby(departed, "Roster test")
    await service.join_lobby(remaining, str(lobby.id))

    await service.leave_lobby(departed, str(lobby.id))

    remaining.connection.send.assert_awaited()
    message = remaining.connection.send.await_args.args[0]
    assert message["serverMessageType"] == "playerUpdate"
    assert [player["uuid"] for player in message["players"]] == [str(remaining.connection.uuid)]


async def test_03_empty_preferences_request_preserves_an_active_game(game, service):
    lobby = await service.create_lobby(game.users[0], "Already started")
    for user in game.users[1:]:
        await service.join_lobby(user, str(lobby.id))
    for user in lobby.users:
        user.is_ready = True
    await lobby.start_game()
    original_game = lobby.game
    original_tiles = lobby.game.tiles
    lobby.game.tiles[0].reveal()

    await MessageRouter(service).route_message(
        context_for(lobby.users[0], lobby), "preferencesRequest", {"player": {}}
    )

    assert lobby.game is original_game, "A preferences read must not replace the active game"
    assert lobby.game.tiles is original_tiles
    assert lobby.game.tiles[0].revealed


async def test_04_ready_player_can_become_unready(service):
    owner = make_user("Owner", Role.RED_SPYMASTER)
    owner.is_ready = True
    lobby = await service.create_lobby(owner, "Ready test")
    await service.join_lobby(make_user("Not ready", Role.BLUE_SPYMASTER), str(lobby.id))

    await MessageRouter(service).route_message(
        context_for(owner, lobby), "preferencesRequest", {"player": {"ready": False}}
    )

    assert owner.is_ready is False, "Explicit false must not be replaced with the previous true value"
    assert lobby.game is None


async def test_04_unnamed_joiner_prevents_game_start(service):
    owner = make_user("Owner", Role.RED_SPYMASTER)
    owner.is_ready = True
    lobby = await service.create_lobby(owner, "Waiting for name")
    await service.join_lobby(make_user(""), str(lobby.id))
    lobby.start_game = AsyncMock()

    await MessageRouter(service).route_message(
        context_for(owner, lobby), "preferencesRequest", {"player": {}}
    )

    lobby.start_game.assert_not_awaited()


async def test_04_lobby_with_no_named_players_does_not_start(service):
    owner = make_user("")
    lobby = await service.create_lobby(owner, "No names yet")
    lobby.start_game = AsyncMock()

    await MessageRouter(service).route_message(
        context_for(owner, lobby), "preferencesRequest", {"player": {}}
    )

    lobby.start_game.assert_not_awaited()


async def test_05_duplicate_correct_guess_does_not_consume_another_guess(game, service):
    game.current_turn = Role.RED_OPERATIVE
    game.guesses_remaining = 3
    operative = game.get_on_turn_user()
    lobby = await service.create_lobby(operative, "Double click")
    lobby.game = game
    context = context_for(operative, lobby)
    router = MessageRouter(service)

    await router.route_message(context, "guessTile", {"word": "APPLE"})
    await router.route_message(context, "guessTile", {"word": "APPLE"})

    assert sum(tile.revealed for tile in game.tiles) == 1
    assert game.guesses_remaining == 2, "Duplicate WebSocket guesses must be idempotent"
    assert game.current_turn == Role.RED_OPERATIVE


@pytest.mark.parametrize(
    "word, number",
    [("FRUIT", "2"), ("FRUIT", -1), ("FRUIT", 1.5), ("FRUIT", True),
     ("FRUIT", 26), ("   ", 2), (123, 2)],
    ids=["string-count", "negative-count", "fractional-count", "boolean-count",
         "count-exceeds-board", "blank-word", "non-string-word"],
)
async def test_06_invalid_clue_is_rejected_without_mutating_game(game, service, word, number):
    spymaster = game.get_on_turn_user()
    lobby = await service.create_lobby(spymaster, "Invalid clue")
    lobby.game = game

    response = await MessageRouter(service).route_message(
        context_for(spymaster, lobby), "provideClue", {"word": word, "number": number}
    )

    # State assertions come first: even an internal-error response must not hide partial mutation.
    assert game.current_turn == Role.RED_SPYMASTER, "Invalid input must not switch the turn"
    assert game.clue is None
    assert game.guesses_remaining == 0
    assert not any(tile.revealed for tile in game.tiles)
    assert response is not None and response["serverMessageType"] == "error"
    assert response["message"] != "Internal server error", "Invalid input needs a validation error"


@pytest.mark.parametrize("operation", ["createLobby", "joinLobby"])
async def test_07_connection_is_not_left_in_multiple_lobbies(service, operation):
    user = make_user("Moving player")
    context = UserContext(user, str(user.connection.uuid))
    router = MessageRouter(service)
    await router.route_message(context, "createLobby", {"name": "First"})
    if operation == "createLobby":
        data = {"name": "Second"}
    else:
        destination = await service.create_lobby(make_user("Other owner"), "Second")
        data = {"lobbyId": str(destination.id)}

    await router.route_message(context, operation, data)
    memberships = [lobby for lobby in await service.repository.list_lobbies() if user in lobby.users]

    assert len(memberships) == 1, "Reject switching or remove the previous membership before switching"
    assert str(memberships[0].id) == context.lobby_id


async def test_07_repeated_join_does_not_duplicate_the_same_user(service):
    owner = make_user("Owner")
    lobby = await service.create_lobby(owner, "Repeated join")
    user = make_user("Joiner")
    context = UserContext(user, str(user.connection.uuid))
    router = MessageRouter(service)

    for _ in range(2):
        await router.route_message(context, "joinLobby", {"lobbyId": str(lobby.id)})

    assert lobby.users.count(user) == 1


async def test_07_disconnect_cleans_all_membership_after_repeated_create(service):
    user = make_user("Double create")
    context = UserContext(user, str(user.connection.uuid))
    router = MessageRouter(service)
    for name in ("First", "Second"):
        await router.route_message(context, "createLobby", {"name": name})

    await WebSocketServer(service, ConnectionManager())._cleanup_connection(context)

    assert not any(user in lobby.users for lobby in await service.repository.list_lobbies()), (
        "Disconnecting must not leave a ghost player in a previous lobby"
    )


# Passing controls show that valid neighboring flows work with the same fixtures.
async def test_control_empty_ai_response_already_passes_the_turn(game):
    game.current_turn = Role.RED_OPERATIVE
    game.guesses_remaining = 3
    operative = game.get_on_turn_user()
    operative.is_human = False
    game.clue_service.gpt_agent.make_guesses = AsyncMock(return_value=[])

    await game.clue_service.make_guesses("FRUIT", 3, game, operative)

    assert game.current_turn == Role.BLUE_SPYMASTER
    assert game.guesses_remaining == 0


async def test_control_valid_clue_and_distinct_guesses_progress_normally(game, service):
    spymaster = game.get_on_turn_user()
    lobby = await service.create_lobby(spymaster, "Valid input")
    lobby.game = game
    router = MessageRouter(service)
    response = await router.route_message(
        context_for(spymaster, lobby), "provideClue", {"word": "FRUIT", "number": 2}
    )
    assert response is None
    assert game.current_turn == Role.RED_OPERATIVE
    assert game.guesses_remaining == 2
    operative = game.get_on_turn_user()
    context = context_for(operative, lobby)

    await router.route_message(context, "guessTile", {"word": "APPLE"})
    assert game.guesses_remaining == 1
    await router.route_message(context, "guessTile", {"word": "ORANGE"})

    assert game.current_turn == Role.BLUE_SPYMASTER
    assert game.guesses_remaining == 0
    assert sum(tile.revealed for tile in game.tiles) == 2
