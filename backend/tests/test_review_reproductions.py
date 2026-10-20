"""Regression specifications for the original reviewed bugs."""

from unittest.mock import AsyncMock

import pytest

from codenames.message_router.message_router import MessageRouter
from codenames.model import Role, Tile
from codenames.websocket_server import WebSocketServer
from tests.helpers import connection_for, context_for, make_runtime, make_service, make_user

pytestmark = pytest.mark.reproduction


@pytest.fixture
def game(monkeypatch):
    monkeypatch.setattr("codenames.game.game.generate_tiles", lambda: [
        Tile("APPLE", "red"), Tile("ORANGE", "red"), Tile("BERRY", "red"),
        Tile("OCEAN", "blue"), Tile("SKY", "blue"), Tile("DEATH", "assassin"),
    ])
    return make_runtime([make_user(role.name, role) for role in Role])


@pytest.fixture
def service():
    return make_service()


@pytest.mark.parametrize("guesses", [["APPLE"], ["APPLE", "NOT ON THE BOARD"]])
async def test_01_ai_passes_after_exhausting_a_short_guess_list(game, guesses):
    game.state.current_turn = Role.RED_OPERATIVE
    game.state.guesses_remaining = 3
    game.state.clue = ("FRUIT", 3)
    operative = game.state.get_on_turn_user()
    operative.is_human = False
    game.ai.make_guesses.return_value = guesses
    await game.make_guesses(operative)
    assert game.state.tiles[0].revealed
    assert game.state.current_turn == Role.BLUE_SPYMASTER
    assert game.state.guesses_remaining == 0
    assert game.state.clue is None


async def test_01_ai_guess_failure_does_not_leave_the_turn_stuck(game):
    game.state.current_turn = Role.RED_OPERATIVE
    game.state.guesses_remaining = 2
    game.state.clue = ("FRUIT", 2)
    operative = game.state.get_on_turn_user()
    operative.is_human = False
    game.ai.make_guesses.side_effect = RuntimeError("AI unavailable")
    await game.make_guesses(operative)
    assert game.state.current_turn == Role.BLUE_SPYMASTER
    assert game.state.guesses_remaining == 0


async def test_01_ai_clue_failure_notifies_humans_instead_of_only_printing(game):
    spymaster = game.state.get_on_turn_user()
    spymaster.is_human = False
    game.ai.provide_clue.side_effect = RuntimeError("AI unavailable")
    await game.create_clue(spymaster)
    delivered = [call.args[0] for user in game.state.users if user.is_human
                 for call in connection_for(user).send.await_args_list]
    assert any(message["serverMessageType"] == "error" for message in delivered)


async def test_02_disconnected_player_is_removed_from_game_roster(game, service):
    users = list(game.state.users)
    lobby = await service.create_lobby(users[0], "Disconnect test")
    for user in users[1:]:
        await service.join_lobby(user, lobby.id)
    lobby.game = make_runtime(lobby.users)
    await WebSocketServer(service)._cleanup_connection(context_for(users[0]))
    assert users[0] not in lobby.users
    assert users[0] not in lobby.game.state.users


async def test_02_broadcast_after_disconnect_reaches_remaining_players(game, service):
    departed = game.state.users[0]
    lobby = await service.create_lobby(departed, "Broadcast test")
    for user in game.state.users[1:]:
        await service.join_lobby(user, lobby.id)
    lobby.game = make_runtime(lobby.users)
    await service.leave_lobby(departed, lobby.id)
    connection_for(departed).send.side_effect = ConnectionError("socket is closed")
    await lobby.game.broadcast_state_update(False)
    connection_for(lobby.users[0]).send.assert_awaited()
    connection_for(departed).send.assert_not_awaited()


async def test_02_lobby_departure_broadcasts_the_updated_roster(service):
    departed = make_user("Departed", Role.RED_SPYMASTER)
    remaining = make_user("Remaining", Role.BLUE_SPYMASTER)
    lobby = await service.create_lobby(departed, "Roster test")
    await service.join_lobby(remaining, lobby.id)
    await service.leave_lobby(departed, lobby.id)
    message = connection_for(remaining).send.await_args.args[0]
    assert message["serverMessageType"] == "playerUpdate"
    assert [player["uuid"] for player in message["players"]] == [remaining.id]


async def test_03_empty_preferences_request_preserves_an_active_game(game, service):
    lobby = await service.create_lobby(game.state.users[0], "Already started")
    for user in game.state.users[1:]:
        await service.join_lobby(user, lobby.id)
    for user in lobby.users:
        user.is_ready = True
    await service.start_game(lobby)
    original = lobby.game
    tiles = original.state.tiles
    tiles[0].reveal()
    await MessageRouter(service).route_message(context_for(lobby.users[0]), "preferencesRequest", {"player": {}})
    assert lobby.game is original
    assert original.state.tiles is tiles
    assert tiles[0].revealed


async def test_04_ready_player_can_become_unready(service):
    owner = make_user("Owner", Role.RED_SPYMASTER)
    owner.is_ready = True
    lobby = await service.create_lobby(owner, "Ready test")
    await service.join_lobby(make_user("Not ready", Role.BLUE_SPYMASTER), lobby.id)
    await MessageRouter(service).route_message(context_for(owner), "preferencesRequest", {"player": {"ready": False}})
    assert not owner.is_ready
    assert lobby.game is None


async def test_04_unnamed_joiner_prevents_game_start(service):
    owner = make_user("Owner", Role.RED_SPYMASTER)
    owner.is_ready = True
    lobby = await service.create_lobby(owner, "Waiting for name")
    await service.join_lobby(make_user(""), lobby.id)
    service.start_game = AsyncMock()
    await MessageRouter(service).route_message(context_for(owner), "preferencesRequest", {"player": {}})
    service.start_game.assert_not_awaited()


async def test_04_lobby_with_no_named_players_does_not_start(service):
    owner = make_user("")
    await service.create_lobby(owner, "No names yet")
    service.start_game = AsyncMock()
    await MessageRouter(service).route_message(context_for(owner), "preferencesRequest", {"player": {}})
    service.start_game.assert_not_awaited()


async def test_05_duplicate_correct_guess_does_not_consume_another_guess(game, service):
    game.state.current_turn = Role.RED_OPERATIVE
    game.state.guesses_remaining = 3
    operative = game.state.get_on_turn_user()
    lobby = await service.create_lobby(operative, "Double click")
    lobby.game = game
    router = MessageRouter(service)
    await router.route_message(context_for(operative), "guessTile", {"word": "APPLE"})
    await router.route_message(context_for(operative), "guessTile", {"word": "APPLE"})
    assert sum(tile.revealed for tile in game.state.tiles) == 1
    assert game.state.guesses_remaining == 2
    assert game.state.current_turn == Role.RED_OPERATIVE


@pytest.mark.parametrize("word, number", [
    ("FRUIT", "2"), ("FRUIT", -1), ("FRUIT", 1.5), ("FRUIT", True),
    ("FRUIT", 26), ("   ", 2), (123, 2),
])
async def test_06_invalid_clue_is_rejected_without_mutating_game(game, service, word, number):
    spymaster = game.state.get_on_turn_user()
    lobby = await service.create_lobby(spymaster, "Invalid clue")
    lobby.game = game
    response = await MessageRouter(service).route_message(
        context_for(spymaster), "provideClue", {"word": word, "number": number},
    )
    assert game.state.current_turn == Role.RED_SPYMASTER
    assert game.state.clue is None
    assert game.state.guesses_remaining == 0
    assert not any(tile.revealed for tile in game.state.tiles)
    assert response["serverMessageType"] == "error"
    assert response["message"] != "Internal server error"


@pytest.mark.parametrize("operation", ["createLobby", "joinLobby"])
async def test_07_connection_is_not_left_in_multiple_lobbies(service, operation):
    user = make_user("Moving player")
    context = context_for(user)
    router = MessageRouter(service)
    await router.route_message(context, "createLobby", {"name": "First"})
    data = {"name": "Second"}
    if operation == "joinLobby":
        destination = await service.create_lobby(make_user("Other owner"), "Second")
        data = {"lobbyId": destination.id}
    await router.route_message(context, operation, data)
    memberships = [lobby for lobby in await service.repository.list_lobbies() if user in lobby.users]
    assert len(memberships) == 1
    assert memberships[0].id == context.lobby_id


async def test_07_repeated_join_does_not_duplicate_the_same_user(service):
    lobby = await service.create_lobby(make_user("Owner"), "Repeated join")
    user = make_user("Joiner")
    for _ in range(2):
        await MessageRouter(service).route_message(context_for(user), "joinLobby", {"lobbyId": lobby.id})
    assert lobby.users.count(user) == 1


async def test_07_disconnect_cleans_all_membership_after_repeated_create(service):
    user = make_user("Double create")
    context = context_for(user)
    for name in ("First", "Second"):
        await MessageRouter(service).route_message(context, "createLobby", {"name": name})
    await WebSocketServer(service)._cleanup_connection(context)
    assert not any(user in lobby.users for lobby in await service.repository.list_lobbies())


async def test_control_empty_ai_response_already_passes_the_turn(game):
    game.state.current_turn = Role.RED_OPERATIVE
    game.state.guesses_remaining = 3
    game.state.clue = ("FRUIT", 3)
    operative = game.state.get_on_turn_user()
    operative.is_human = False
    game.ai.make_guesses.return_value = []
    await game.make_guesses(operative)
    assert game.state.current_turn == Role.BLUE_SPYMASTER
    assert game.state.guesses_remaining == 0


async def test_control_valid_clue_and_distinct_guesses_progress_normally(game, service):
    spymaster = game.state.get_on_turn_user()
    lobby = await service.create_lobby(spymaster, "Valid input")
    lobby.game = game
    router = MessageRouter(service)
    response = await router.route_message(context_for(spymaster), "provideClue", {"word": "FRUIT", "number": 2})
    assert response is None
    assert game.state.current_turn == Role.RED_OPERATIVE
    assert game.state.guesses_remaining == 2
    operative = game.state.get_on_turn_user()
    # All game participants must also be room members to send public commands.
    lobby.users.append(operative)
    service._set_membership(operative, lobby.id)
    await router.route_message(context_for(operative), "guessTile", {"word": "APPLE"})
    assert game.state.guesses_remaining == 1
    await router.route_message(context_for(operative), "guessTile", {"word": "ORANGE"})
    assert game.state.current_turn == Role.BLUE_SPYMASTER
    assert game.state.guesses_remaining == 0
    assert sum(tile.revealed for tile in game.state.tiles) == 2
