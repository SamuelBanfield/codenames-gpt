"""Behavioral checks for state/runtime, session, and delivery ownership."""

import asyncio
import json
import os
import subprocess
import sys
from contextlib import AsyncExitStack
from unittest.mock import AsyncMock

import pytest
import websockets

from codenames.game.factory import create_ai_user
from codenames.model import Role, Tile
from codenames.websocket_server import WebSocketServer
from tests.helpers import connection_for, context_for, make_runtime, make_service, make_user


def test_rules_can_run_without_credentials_or_ai_imports():
    environment = os.environ.copy()
    environment.pop("OPENAI_KEY", None)
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
    runtime = make_runtime(users)
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
    runtime = make_runtime(users)
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
    runtime = make_runtime(users)
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
    assert await service.repository.list_lobbies() == []
