"""Behavioral checks for state/runtime, session, and delivery ownership."""

import asyncio
import json
import os
import subprocess
import sys
from contextlib import AsyncExitStack
from unittest.mock import AsyncMock, Mock

import pytest
import websockets

from codenames.game.factory import create_ai_user, create_game
from codenames.game.runtime import GameRuntime
from codenames.messages import MessageRouter
from codenames.model import Role, Tile
from codenames.websocket_server import WebSocketConnection, WebSocketServer
from tests.helpers import connection_for, context_for, make_runtime, make_service, make_user


def test_rules_can_run_without_credentials_or_ai_imports():
    environment = os.environ.copy()
    environment.pop("OPENAI_API_KEY", None)
    result = subprocess.run([sys.executable, "-c", "\n".join([
        "import sys",
        "from codenames.game.game import CodenamesGame",
        "from codenames.model import Role, User",
        "users = [User(role=role) for role in Role]",
        "game = CodenamesGame(users)",
        "assert game.provide_clue(users[0], 'CLUE', 1)",
        "assert game.current_turn == Role.RED_OPERATIVE",
        "assert 'openai' not in sys.modules",
        "assert 'codenames.options' not in sys.modules",
    ])], env=environment, capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("role", list(Role))
def test_role_wire_mapping_and_transport_free_ai(role):
    user = create_ai_user(role)
    assert user.role is role
    assert user.team == role.team
    assert user.is_spy_master == role.is_spymaster
    assert user.to_json()["role"] == role.index
    assert not hasattr(user, "connection")
    assert not hasattr(user, "in_game")
    assert not hasattr(user, "in_lobby")


async def test_runtime_lazily_creates_one_client_and_closes_it_once():
    users = [make_user(role.name, role) for role in Role]
    runtime = await make_runtime(users)
    runtime._ai_factory.assert_not_called()
    await runtime.provide_clue(users[0], "FIRST", 1)
    await runtime.pass_turn(users[2])
    runtime._ai_factory.assert_not_called()
    users[1].is_human = False
    await runtime.create_clue(users[1])
    runtime._ai_factory.assert_called_once()
    client = runtime.ai
    await runtime.dispose()
    await runtime.dispose()
    client.close.assert_awaited_once()


async def test_winning_move_closes_existing_client_without_creating_another():
    users = [make_user(role.name, role) for role in Role]
    runtime = await make_runtime(users)
    client = runtime.ai
    runtime.state.tiles = [Tile("RED", "red"), Tile("BLUE", "blue"), Tile("KILL", "assassin")]
    await runtime.provide_clue(users[0], "CLUE", 1)
    await runtime.guess_tile(users[2], runtime.state.tiles[0])
    assert runtime.state.winner == "red"
    client.close.assert_awaited_once()
    await runtime.dispose()
    runtime._ai_factory.assert_called_once()
    client.close.assert_awaited_once()


async def test_membership_and_flags_are_updated_before_departure_delivery():
    service = make_service()
    owner = make_user("Owner", Role.RED_SPYMASTER)
    remaining = make_user("Remaining", Role.BLUE_SPYMASTER)
    lobby = await service.create_lobby(owner, "Membership")
    await service.join_lobby(remaining, lobby.id)
    await service.start_game(lobby)
    sending, release = asyncio.Event(), asyncio.Event()

    async def held_send(message):
        sending.set()
        await release.wait()

    connection_for(remaining).send.side_effect = held_send
    task = asyncio.create_task(service.leave_lobby(owner, lobby.id))
    try:
        await asyncio.wait_for(sending.wait(), 1)
        assert context_for(owner).lobby_id is None
        assert owner.role is None and not owner.is_ready
        assert owner not in lobby.users and owner not in lobby.game.state.users
        roster = lobby.get_player_update()["players"]
        assert len(roster) == 1 and roster[0]["inLobby"] and roster[0]["inGame"]
    finally:
        release.set()
        await task
        await lobby.game.dispose()


async def test_preferences_validate_before_mutation_in_room_coordinator():
    service = make_service()
    first = make_user("First", Role.RED_SPYMASTER)
    second = make_user("Second", Role.BLUE_SPYMASTER)
    lobby = await service.create_lobby(first, "Preferences")
    await service.join_lobby(second, lobby.id)
    with pytest.raises(ValueError, match="occupied"):
        await service.update_preferences(second, lobby.id, {"name": "CHANGED", "role": 0, "ready": True})
    assert second.name == "Second"
    assert second.role is Role.BLUE_SPYMASTER
    assert not second.is_ready
    await service.update_preferences(second, lobby.id, {"role": 3, "ready": False})
    assert second.role is Role.BLUE_OPERATIVE
    assert lobby.game is None


async def test_shared_delivery_keeps_board_projection_recipient_specific():
    users = [make_user(role.name, role) for role in Role]
    runtime = await make_runtime(users)
    runtime.state.tiles[0].reveal()
    await runtime.broadcast_state_update(False)
    for user in users:
        frame = connection_for(user).send.await_args.args[0]
        assert frame["players"][0]["uuid"] == users[0].id
        assert all(player["inGame"] for player in frame["players"])
        assert frame["tiles"][0]["team"] != "unknown"
        hidden = [tile for tile in frame["tiles"] if not tile["revealed"]]
        assert all((tile["team"] != "unknown") == user.is_spy_master for tile in hidden)


async def test_slow_recipient_does_not_block_healthy_recipient_or_ai_progress():
    service = make_service()
    service.connections.send_timeout = 0.05
    slow = make_user("Slow", Role.RED_SPYMASTER)
    human = make_user("Operative", Role.RED_OPERATIVE)
    lobby = await service.create_lobby(slow, "Slow recipient")
    await service.join_lobby(human, lobby.id)
    await service.start_game(lobby)
    await lobby.game.provide_clue(slow, "CLUE", 1)
    delivered = asyncio.Event()
    stuck = asyncio.Event()

    async def stalled_send(message):
        await stuck.wait()

    async def healthy_send(message):
        delivered.set()

    connection_for(slow).send.side_effect = stalled_send
    connection_for(human).send.side_effect = healthy_send
    lobby.game.create_clue = AsyncMock()
    task = asyncio.create_task(lobby.game.pass_turn(human))
    try:
        await asyncio.wait_for(delivered.wait(), 1)
        await asyncio.wait_for(task, 1)
        await asyncio.sleep(0)
        lobby.game.create_clue.assert_awaited_once()
    finally:
        stuck.set()
        await task
        await lobby.game.dispose()


async def test_delivery_serializes_frames_for_one_connection():
    service = make_service()
    user = make_user()
    entered, release = asyncio.Event(), asyncio.Event()
    received = []

    async def send(message):
        if message["number"] == 1:
            entered.set()
            await release.wait()
        received.append(message["number"])

    connection_for(user).send.side_effect = send
    first = asyncio.create_task(service.connections.send(user.id, {"number": 1}))
    await asyncio.wait_for(entered.wait(), 1)
    second = asyncio.create_task(service.connections.send(user.id, {"number": 2}))
    release.set()
    assert all(await asyncio.gather(first, second))
    assert received == [1, 2]


async def test_real_websocket_player_protocol_still_starts_and_advances_game():
    service = make_service()
    server = WebSocketServer(service)

    async def receive_kind(socket, kind):
        async with asyncio.timeout(2):
            while True:
                frame = json.loads(await socket.recv())
                if frame["serverMessageType"] == kind:
                    return frame

    async def send(socket, kind, **payload):
        await socket.send(json.dumps({"clientMessageType": kind, **payload}))

    async with websockets.serve(server.handle_connection, "127.0.0.1", 0) as listener:
        port = listener.sockets[0].getsockname()[1]
        async with AsyncExitStack() as stack:
            sockets = [await stack.enter_async_context(websockets.connect(f"ws://127.0.0.1:{port}"))
                       for _ in Role]
            ids = []
            for socket in sockets:
                await send(socket, "idRequest")
                ids.append((await receive_kind(socket, "idAssign"))["uuid"])
            await send(sockets[0], "createLobby", name="Protocol")
            lobby_id = (await receive_kind(sockets[0], "lobbyJoined"))["lobbyId"]
            for socket in sockets[1:]:
                await send(socket, "joinLobby", lobbyId=lobby_id)
                assert (await receive_kind(socket, "lobbyJoined"))["lobbyId"] == lobby_id
            # Acknowledge each preference mutation before making everyone ready.
            for index, socket in enumerate(sockets):
                await send(socket, "preferencesRequest", player={"name": f"Human {index}", "role": index})
                async with asyncio.timeout(2):
                    while True:
                        frame = await receive_kind(socket, "playerUpdate")
                        if any(p["uuid"] == ids[index] and p["role"] == index for p in frame["players"]):
                            break
            for socket in sockets:
                await send(socket, "preferencesRequest", player={"ready": True})
            states = [await receive_kind(socket, "stateUpdate") for socket in sockets]
            assert all(frame["phase"] == "active" and frame["onTurnRole"] == 0 for frame in states)
            assert all(tile["team"] == "unknown" for tile in states[2]["tiles"])
            red_word = next(tile["word"] for tile in states[0]["tiles"] if tile["team"] == "red")
            await send(sockets[0], "provideClue", word="CLUE", number=2,
                       gameId=states[0]["gameId"], turnId=states[0]["turnId"])
            clue_states = [await receive_kind(socket, "stateUpdate") for socket in sockets]
            assert all(frame["onTurnRole"] == 2 for frame in clue_states)
            await send(sockets[2], "guessTile", word=red_word,
                       gameId=clue_states[2]["gameId"], turnId=clue_states[2]["turnId"])
            guessed = [await receive_kind(socket, "stateUpdate") for socket in sockets]
            assert all(frame["guessesRemaining"] == 1 for frame in guessed)
            assert all(next(tile for tile in frame["tiles"] if tile["word"] == red_word)["revealed"]
                       for frame in guessed)
            await send(sockets[1], "guessTile", word=red_word)
            assert (await receive_kind(sockets[1], "error"))["message"] == "It is not your operative turn"
    assert service.list_lobbies() == []


async def test_room_queries_are_direct_reads_and_return_independent_lists():
    rooms = make_service()
    first = make_user("First")
    second = make_user("Second")
    lobby = await rooms.create_lobby(first, "Rooms")
    await rooms.join_lobby(second, lobby.id)
    assert rooms.get_lobby(lobby.id) is lobby
    assert rooms.get_lobby("missing") is None
    listed = rooms.list_lobbies()
    listed.clear()
    assert rooms.list_lobbies() == [lobby]
    assert not hasattr(lobby, "lobby_owner")
    await rooms.leave_lobby(first, lobby.id)
    assert rooms.get_lobby(lobby.id) is lobby
    assert lobby.users == [second]
    assert context_for(first).lobby_id is None


async def test_lobby_list_dispatch_keeps_full_and_started_rooms_hidden():
    rooms = make_service()
    users = [make_user(role.name, role) for role in Role]
    lobby = await rooms.create_lobby(users[0], "Available")
    router = MessageRouter(rooms)
    session = context_for(users[0])
    assert (await router.route_message(session, "lobbiesRequest", {}))["lobbies"] == [lobby.to_json()]
    for user in users[1:]:
        await rooms.join_lobby(user, lobby.id)
    assert rooms.get_available_lobbies() == []
    await rooms.leave_lobby(users[3], lobby.id)
    assert rooms.get_available_lobbies() == [lobby]
    await rooms.start_game(lobby)
    try:
        assert rooms.list_lobbies() == [lobby]
        assert (await router.route_message(session, "lobbiesRequest", {}))["lobbies"] == []
    finally:
        await lobby.game.dispose()


def test_plain_game_factory_fills_roles_without_mutating_human_list():
    human = make_user("Human", Role.BLUE_OPERATIVE)
    humans = [human]
    game = create_game(humans)
    assert humans == [human]
    assert game.users[0] is human
    assert len(game.users) == 4
    assert {user.role for user in game.users} == set(Role)
    assert all(not user.is_human for user in game.users[1:])


@pytest.mark.parametrize("command", [
    "preferencesRequest", "initialiseRequest", "guessTile", "provideClue", "retryAI",
])
@pytest.mark.parametrize("context", ["no-room", "missing-room", "non-member"])
async def test_dispatch_preserves_context_errors(command, context):
    rooms = make_service()
    user = make_user()
    session = context_for(user)
    expected = "User not in a lobby"
    if context == "missing-room":
        session.lobby_id = "missing"
        expected = "Lobby not found"
    elif context == "non-member":
        other_room = await rooms.create_lobby(make_user("Other"), "Other")
        session.lobby_id = other_room.id
        expected = "User not in this lobby"
    if command == "initialiseRequest" and context != "no-room":
        expected = "Lobby membership not found"
    result = await MessageRouter(rooms).route_message(session, command, {})
    assert result == {"serverMessageType": "stateError", "message": expected}


@pytest.mark.parametrize("command", ["guessTile", "provideClue", "retryAI"])
async def test_dispatch_requires_a_game_for_game_commands(command):
    rooms = make_service()
    user = make_user()
    await rooms.create_lobby(user, "Waiting")
    result = await MessageRouter(rooms).route_message(context_for(user), command, {})
    assert result == {"serverMessageType": "stateError", "message": "Game not found"}


async def test_dispatch_still_rejects_unknown_and_malformed_requests():
    rooms = make_service()
    user = make_user()
    session = context_for(user)
    router = MessageRouter(rooms)
    result = await router.route_message(session, "unknown", {})
    assert result == {"serverMessageType": "error", "message": "Unknown message type: unknown"}
    invalid = await router.route_message(session, "createLobby", {"name": " "})
    assert invalid["code"] == "invalidRequest"
    assert rooms.list_lobbies() == []
    lobby = await rooms.create_lobby(user, "Waiting")
    invalid = await router.route_message(session, "preferencesRequest", {"player": []})
    assert invalid["message"] == "Player preferences must be an object"
    assert not user.is_ready and user.role is None and lobby.game is None


async def test_transport_has_no_identity_and_protocol_uses_player_uuid():
    rooms = make_service()
    user = make_user()
    socket = Mock()
    socket.send = AsyncMock()
    connection = WebSocketConnection(socket)
    assert not hasattr(connection, "id")
    session = context_for(user)
    assert not hasattr(session, "connection_id")
    response = await MessageRouter(rooms).route_message(session, "idRequest", {})
    assert response == {"serverMessageType": "idAssign", "uuid": user.id}
    await connection.send(response)
    assert json.loads(socket.send.await_args.args[0]) == response


async def test_runtime_activation_is_once_only_and_owns_startup_state():
    rooms = make_service()
    users = [make_user(role.name, role) for role in Role]
    runtime = GameRuntime(create_game(users), rooms.connections, rooms.ai_factory, 0, lobby_id="room")
    assert not runtime.started
    assert runtime.state.revision == 0
    assert runtime.get_state_update(users[0], False)["phase"] == "starting"
    assert runtime.get_state_update(users[0], False)["lobbyId"] == "room"
    with pytest.raises(ValueError, match="not ready"):
        runtime.validate_action({})
    sending, release = asyncio.Event(), asyncio.Event()

    async def held_broadcast(new_turn):
        sending.set()
        await release.wait()

    runtime.broadcast_state_update = AsyncMock(side_effect=held_broadcast)
    runtime.schedule_ai_turn = Mock()
    first = asyncio.create_task(runtime.activate())
    try:
        await asyncio.wait_for(sending.wait(), 1)
        await runtime.activate()
        assert runtime.started
        assert runtime.state.revision == 1
        runtime.broadcast_state_update.assert_awaited_once_with(True)
        runtime.schedule_ai_turn.assert_not_called()
    finally:
        release.set()
        await first
        await runtime.dispose()
    runtime.schedule_ai_turn.assert_called_once_with(runtime.state.turn_id)
    rooms.ai_factory.assert_not_called()


@pytest.mark.parametrize("terminal", ["disposed", "finished"])
async def test_runtime_cannot_activate_after_disposal_or_completion(terminal):
    rooms = make_service()
    users = [make_user(role.name, role) for role in Role]
    runtime = GameRuntime(create_game(users), rooms.connections, rooms.ai_factory, 0, lobby_id="room")
    runtime.broadcast_state_update = AsyncMock()
    if terminal == "disposed":
        await runtime.dispose()
    else:
        for tile in runtime.state.tiles:
            if tile.team == "red":
                tile.reveal()
    await runtime.activate()
    assert not runtime.started
    assert runtime.state.revision == 0
    assert not runtime._tasks
    runtime.broadcast_state_update.assert_not_awaited()
    rooms.ai_factory.assert_not_called()


async def test_disposal_during_activation_delivery_prevents_ai_startup():
    rooms = make_service()
    human = make_user("Blue spymaster", Role.BLUE_SPYMASTER)
    runtime = GameRuntime(create_game([human]), rooms.connections, rooms.ai_factory, 0, lobby_id="room")
    sending, release = asyncio.Event(), asyncio.Event()

    async def held_broadcast(new_turn):
        sending.set()
        await release.wait()

    runtime.broadcast_state_update = held_broadcast
    task = asyncio.create_task(runtime.activate())
    try:
        await asyncio.wait_for(sending.wait(), 1)
        await runtime.dispose()
    finally:
        release.set()
        await task
    assert runtime.disposed
    assert not runtime._tasks
    rooms.ai_factory.assert_not_called()
