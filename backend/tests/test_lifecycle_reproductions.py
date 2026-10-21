"""Endgame and late-request regression specifications, plus passing controls.

Regressions assert correct behavior. Events hold specific API/send boundaries so
concurrency cases do not depend on timing.
"""

import asyncio
import json
from unittest.mock import AsyncMock, patch

import pytest

from codenames.messages import MessageRouter
from codenames.model import Role, Tile
from tests.helpers import make_user, make_runtime, make_service, context_for, connection_for
from codenames.websocket_server import WebSocketServer


pytestmark = pytest.mark.reproduction


@pytest.fixture
def make_game(monkeypatch):
    def generate_tiles():
        return [
            Tile("RED1", "red"), Tile("RED2", "red"),
            Tile("BLUE1", "blue"), Tile("BLUE2", "blue"),
            Tile("KILL", "assassin"), Tile("NEUTRAL", "neutral"),
        ]

    monkeypatch.setattr("codenames.game.game.generate_tiles", generate_tiles)

    async def create(users=None):
        return await make_runtime(
            users if users is not None else [make_user(role.name, role) for role in Role]
        )

    return create


@pytest.fixture
def service(make_game):
    return make_service()


@pytest.fixture
async def tasks():
    owned = []
    yield owned
    for task in owned:
        if not task.done():
            task.cancel()
    await asyncio.gather(*owned, return_exceptions=True)


async def checkpoint(event):
    # A timeout identifies a broken test schedule, rather than hanging the suite.
    await asyncio.wait_for(event.wait(), timeout=2)


def capture_game_tasks(owned):
    """Observe real game scheduling while leaving task execution unchanged."""
    create_task = asyncio.create_task

    def spawn(coroutine, *args, **kwargs):
        task = create_task(coroutine, *args, **kwargs)
        owned.append(task)
        return task

    return patch("codenames.game.runtime.asyncio.create_task", side_effect=spawn)


async def start_room(service, users):
    lobby = await service.create_lobby(users[0], "Lifecycle test")
    for user in users[1:]:
        assert await service.join_lobby(user, str(lobby.id)) is lobby
    await service.start_game(lobby)
    return lobby


def prepare_terminal_guess(game, team, target):
    game.state.current_turn = Role.from_team_and_role(team, False)
    game.state.guesses_remaining = 1
    opponent = "blue" if team == "red" else "red"
    tile_team = team if target == "own" else opponent if target == "opponent" else "assassin"
    tile = next(tile for tile in game.state.tiles if tile.team == tile_team)
    if target != "assassin":
        for other in game.state.tiles:
            if other.team == tile_team and other is not tile:
                other.reveal()
    assert game.state.check_win() is None
    return game.state.get_on_turn_user(), tile, team if target == "own" else opponent


@pytest.mark.parametrize("team", ["red", "blue"])
@pytest.mark.parametrize("target", ["own", "opponent", "assassin"])
async def test_winning_guess_does_not_request_another_ai_clue(make_game, team, target):
    game = await make_game()
    operative, tile, expected_winner = prepare_terminal_guess(game, team, target)
    next_spymaster = next(user for user in game.state.users if user.team != team and user.is_spy_master)
    next_spymaster.is_human = False

    await game.guess_tile(operative, tile)
    # Let any newly scheduled coroutine start; no elapsed-time delay is involved.
    await asyncio.sleep(0)

    assert game.state.check_win() == expected_winner
    game._ai_factory.return_value.provide_clue.assert_not_awaited()


async def test_clue_service_checks_completion_before_requesting_ai(make_game):
    game = await make_game()
    for tile in game.state.tiles:
        if tile.team == "red":
            tile.reveal()

    await game.create_clue(game.state.get_on_turn_user())

    game._ai_factory.return_value.provide_clue.assert_not_awaited()


async def test_ai_guess_loop_stops_immediately_after_a_winning_guess(make_game):
    game = await make_game()
    operative, winning_tile, _ = prepare_terminal_guess(game, "red", "own")
    game.state.guesses_remaining = 3
    game.state.clue = ("CLUE", 3)
    operative.is_human = False
    game.ai.make_guesses.return_value = [winning_tile.word, "BLUE1"]
    game.guess_tile = AsyncMock(wraps=game.guess_tile)

    await game.make_guesses(operative)

    assert game.state.check_win() == "red"
    assert game.guess_tile.await_count == 1, "An AI loop must stop, rather than submit ignored postgame guesses"


async def test_internal_pass_cannot_mutate_a_completed_game(make_game):
    game = await make_game()
    operative, tile, _ = prepare_terminal_guess(game, "red", "own")
    game.state.guesses_remaining = 2
    game.state.clue = ("CLUE", 2)
    await game.guess_tile(operative, tile)
    completed = game.get_state_update(operative, False)

    await game.pass_turn(operative)

    assert game.get_state_update(operative, False) == completed


async def test_empty_preferences_preserves_a_completed_game(service):
    owner = make_user("Owner", Role.RED_SPYMASTER)
    owner.is_ready = True
    lobby = await start_room(service, [owner])
    completed = lobby.game
    for tile in completed.state.tiles:
        if tile.team == "red":
            tile.reveal()
    assert completed.state.check_win() == "red"

    await MessageRouter(service).route_message(
        context_for(owner, lobby), "preferencesRequest", {"player": {}}
    )

    assert lobby.game is completed
    assert lobby.game.state.check_win() == "red"


async def test_pending_old_ai_cannot_publish_a_win_for_a_replacement_game(service, tasks):
    owner = make_user("Owner", Role.RED_SPYMASTER)
    owner.is_ready = True
    lobby = await start_room(service, [owner])
    old = lobby.game
    old.state.tiles = [Tile("OLDRED", "red"), Tile("OLDBLUE", "blue"), Tile("OLDKILL", "assassin")]
    requested, release = asyncio.Event(), asyncio.Event()

    async def delayed_guesses(*args):
        requested.set()
        await release.wait()
        return ["OLDRED"]

    old.ai.make_guesses.side_effect = delayed_guesses
    with capture_game_tasks(tasks):
        await old.provide_clue(owner, "CLUE", 1)
    task = tasks[-1]
    await checkpoint(requested)
    await MessageRouter(service).route_message(
        context_for(owner, lobby), "preferencesRequest", {"player": {}}
    )
    current = lobby.game
    connection_for(owner).send.reset_mock()
    release.set()
    await asyncio.wait_for(asyncio.gather(task, return_exceptions=True), timeout=2)
    await asyncio.sleep(0)

    # Preventing the replacement or invalidating the old task are both valid fixes.
    if current is not old:
        states = [call.args[0] for call in connection_for(owner).send.await_args_list
                  if call.args[0].get("serverMessageType") == "stateUpdate"]
        assert not any(state["tiles"][0]["word"] == "OLDRED" for state in states), (
            "A superseded game must not publish its board or winner to current players"
        )


async def test_last_human_departure_terminates_pending_ai_work(service, tasks):
    owner = make_user("Owner", Role.RED_SPYMASTER)
    lobby = await start_room(service, [owner])
    game = lobby.game
    requested, release = asyncio.Event(), asyncio.Event()

    async def delayed_guesses(*args):
        requested.set()
        await release.wait()
        return []

    game.ai.make_guesses.side_effect = delayed_guesses
    with capture_game_tasks(tasks):
        await game.provide_clue(owner, "CLUE", 1)
    task = tasks[-1]
    await checkpoint(requested)

    await service.leave_lobby(owner, str(lobby.id))
    await asyncio.sleep(0)

    assert service.get_lobby(str(lobby.id)) is None
    assert task.done(), "Deleting an abandoned lobby must terminate its pending game work"


async def test_second_preferences_during_startup_does_not_replace_the_game(service, tasks):
    owner = make_user("Owner", Role.RED_SPYMASTER)
    other = make_user("Other", Role.BLUE_SPYMASTER)
    owner.is_ready = other.is_ready = True
    lobby = await service.create_lobby(owner, "Starting")
    await service.join_lobby(other, str(lobby.id))
    sending, release = asyncio.Event(), asyncio.Event()
    calls = 0

    async def hold_first_roster(message):
        nonlocal calls
        calls += 1
        if calls == 1:
            sending.set()
            await release.wait()

    connection_for(owner).send.side_effect = hold_first_roster
    router = MessageRouter(service)
    first = asyncio.create_task(router.route_message(
        context_for(owner, lobby), "preferencesRequest", {"player": {}}
    ))
    tasks.append(first)
    await checkpoint(sending)
    published = lobby.game
    assert published is not None

    await router.route_message(context_for(other, lobby), "preferencesRequest", {"player": {}})
    release.set()
    await asyncio.wait_for(first, timeout=2)

    assert lobby.game is published, "Another connection's late preferences must not restart startup"


async def test_turn_advance_during_broadcast_does_not_schedule_a_clue_for_an_operative(make_game, tasks):
    game = await make_game()
    game.state.current_turn = Role.RED_OPERATIVE
    game.state.guesses_remaining = 1
    blue_operative = next(user for user in game.state.users if user.team == "blue" and not user.is_spy_master)
    blue_operative.is_human = False
    game.create_clue = AsyncMock()
    game.make_guesses = AsyncMock()
    sending, release = asyncio.Event(), asyncio.Event()
    calls = 0

    async def hold_first_broadcast(*args):
        nonlocal calls
        calls += 1
        if calls == 1:
            sending.set()
            await release.wait()

    game.broadcast_state_update = hold_first_broadcast
    task = asyncio.create_task(game.guess_tile(
        game.state.get_on_turn_user(), next(tile for tile in game.state.tiles if tile.team == "neutral")
    ))
    tasks.append(task)
    await checkpoint(sending)
    await game.provide_clue(game.state.get_on_turn_user(), "BLUECLUE", 1)
    release.set()
    await asyncio.wait_for(task, timeout=2)
    await asyncio.sleep(0)

    assert game.state.current_turn == Role.BLUE_OPERATIVE
    assert all(call.args[0].is_spy_master for call in game.create_clue.await_args_list), (
        "Post-broadcast scheduling must still refer to the transition that initiated it"
    )


async def test_failed_recipient_does_not_stop_next_ai_turn(make_game, service):
    game = await make_game()
    game.state.current_turn = Role.RED_OPERATIVE
    game.state.guesses_remaining = 1
    departed = next(user for user in game.state.users if user.team == "red" and user.is_spy_master)
    connection_for(departed).send.side_effect = ConnectionError("socket closed before cleanup")
    blue_spymaster = next(user for user in game.state.users if user.team == "blue" and user.is_spy_master)
    blue_spymaster.is_human = False
    game.create_clue = AsyncMock()
    operative = game.state.get_on_turn_user()
    lobby = await service.create_lobby(operative, "Send failure")
    lobby.game = game

    await MessageRouter(service).route_message(
        context_for(operative, lobby), "guessTile", {"word": "NEUTRAL"}
    )
    await asyncio.sleep(0)

    assert game.state.current_turn == Role.BLUE_SPYMASTER
    game.create_clue.assert_awaited_once_with(blue_spymaster)


@pytest.mark.parametrize("operation", ["createLobby", "joinLobby"])
async def test_postgame_lobby_transition_does_not_inherit_readiness_or_in_game(service, operation):
    owner = make_user("Owner", Role.RED_SPYMASTER)
    owner.is_ready = True
    lobby = await start_room(service, [owner])
    for tile in lobby.game.state.tiles:
        if tile.team == "red":
            tile.reveal()
    context = context_for(owner, lobby)
    if operation == "createLobby":
        data = {"name": "New room"}
    else:
        destination = await service.create_lobby(make_user("Other owner"), "New room")
        data = {"lobbyId": str(destination.id)}

    await MessageRouter(service).route_message(context, operation, data)

    # An explicit rejection is also safe; flags must reset if switching is accepted.
    if context.lobby_id != str(lobby.id):
        new_lobby = service.get_lobby(context.lobby_id)
        assert not any(player["inGame"] for player in new_lobby.get_player_update()["players"])
        assert owner.is_ready is False


async def test_name_confirmation_in_a_new_room_does_not_autostart_from_old_readiness(service):
    owner = make_user("Owner", Role.RED_SPYMASTER)
    owner.is_ready = True
    old = await start_room(service, [owner])
    for tile in old.game.state.tiles:
        if tile.team == "red":
            tile.reveal()
    context = context_for(owner, old)
    router = MessageRouter(service)
    await router.route_message(context, "createLobby", {"name": "Next room"})
    if context.lobby_id == str(old.id):
        return  # Switching was rejected rather than silently carrying old state.
    new = service.get_lobby(context.lobby_id)
    assert new.game is None

    await router.route_message(context, "preferencesRequest", {"player": {"name": "New name"}})

    assert new.game is None, "Confirming a name must not reuse readiness from the finished game"


async def test_late_role_preferences_cannot_claim_an_ai_role_or_expose_hidden_tiles(service):
    owner = make_user("Unassigned")
    lobby = await service.create_lobby(owner, "Published roles")
    # Keep the initial AI spymaster idle while exercising preference authorization.
    with patch("codenames.game.runtime.GameRuntime.create_clue", new_callable=AsyncMock):
        await service.start_game(lobby)
        await asyncio.sleep(0)
    game = lobby.game
    assert owner.is_spy_master is False
    assert all(tile["team"] == "unknown" for tile in game.get_state_update(owner, False)["tiles"])

    await MessageRouter(service).route_message(
        context_for(owner, lobby), "preferencesRequest",
        {"player": {"name": "Human", "ready": False, "role": Role.RED_SPYMASTER.index}},
    )

    assert lobby.game is game
    assert owner.is_spy_master is False, "Published game roles cannot be reassigned through lobby preferences"
    assert all(tile["team"] == "unknown" for tile in game.get_state_update(owner, False)["tiles"])


# Controls preserve behavior that the investigation found correct.
@pytest.mark.parametrize("team", ["red", "blue"])
@pytest.mark.parametrize("target", ["own", "opponent", "assassin"])
async def test_control_terminal_guess_awards_the_correct_winner_and_rejects_later_guesses(make_game, team, target):
    game = await make_game()
    operative, tile, expected = prepare_terminal_guess(game, team, target)
    await game.guess_tile(operative, tile)
    assert game.state.check_win() == expected
    revealed = [tile.revealed for tile in game.state.tiles]

    await game.guess_tile(operative, next(tile for tile in game.state.tiles if tile.team == "neutral"))

    assert [tile.revealed for tile in game.state.tiles] == revealed


async def test_control_join_is_rejected_after_publication_while_startup_send_is_pending(service, tasks):
    owner = make_user("Owner", Role.RED_SPYMASTER)
    lobby = await service.create_lobby(owner, "Published startup")
    sending, release = asyncio.Event(), asyncio.Event()

    async def held_send(message):
        if message["serverMessageType"] == "playerUpdate":
            sending.set()
            await release.wait()

    connection_for(owner).send.side_effect = held_send
    task = asyncio.create_task(service.start_game(lobby))
    tasks.append(task)
    await checkpoint(sending)

    assert lobby.game is not None
    assert await service.join_lobby(make_user("Late join"), str(lobby.id)) is None
    release.set()
    await asyncio.wait_for(task, timeout=2)


async def test_control_same_connection_waits_for_prior_response_delivery(service, tasks):
    server = WebSocketServer(service)
    routed = []
    sending, release = asyncio.Event(), asyncio.Event()

    async def route(context, kind, data):
        routed.append(kind)
        return {"serverMessageType": "ack"}

    server.message_router.route_message = AsyncMock(side_effect=route)

    class Socket:
        def __init__(self):
            self.received = 0
            self.sent = 0

        def __aiter__(self):
            return self.messages()

        async def messages(self):
            for kind in ("idRequest", "lobbiesRequest"):
                self.received += 1
                yield json.dumps({"clientMessageType": kind})

        async def send(self, message):
            self.sent += 1
            if self.sent == 1:
                sending.set()
                await release.wait()

    socket = Socket()
    task = asyncio.create_task(server.handle_connection(socket, "/"))
    tasks.append(task)
    await checkpoint(sending)
    assert routed == ["idRequest"]
    assert socket.received == 1
    release.set()
    await asyncio.wait_for(task, timeout=2)
    assert routed == ["idRequest", "lobbiesRequest"]


@pytest.mark.parametrize("role", [Role.RED_SPYMASTER, Role.RED_OPERATIVE])
async def test_departed_on_turn_human_is_replaced_by_ai_and_play_resumes(service, tasks, role):
    departed = make_user("Departed", role)
    humans = [departed] + [make_user(other.name, other) for other in Role if other != role]
    lobby = await start_room(service, humans)
    game = lobby.game
    if not role.is_spymaster:
        await game.provide_clue(game.state.get_on_turn_user(), "CLUE", 2)
    turn = game.state.turn_id
    requested, release = asyncio.Event(), asyncio.Event()

    async def held_response(*args):
        requested.set()
        await release.wait()
        return ("TAKEOVER", 1) if role.is_spymaster else ["RED1"]

    agent = game.ai
    (agent.provide_clue if role.is_spymaster else agent.make_guesses).side_effect = held_response
    connection_for(departed).send.reset_mock()
    with capture_game_tasks(tasks):
        await service.leave_lobby(departed, str(lobby.id))
    await checkpoint(requested)
    replacement = game.state.get_on_turn_user()
    assert not replacement.is_human
    assert (replacement.team, replacement.is_spy_master) == role.value
    assert game.state.turn_id > turn
    assert departed not in game.state.users and departed not in lobby.users
    connection_for(departed).send.assert_not_awaited()

    release.set()
    await asyncio.wait_for(asyncio.gather(*tasks), timeout=2)
    assert game.state.get_on_turn_user().is_human
    if role.is_spymaster:
        assert game.state.current_turn == Role.RED_OPERATIVE
        assert game.state.clue == ("TAKEOVER", 1)
    else:
        assert game.state.current_turn == Role.BLUE_SPYMASTER
        assert game.state.tiles[0].revealed


async def test_finished_game_departure_does_not_create_an_ai_replacement(service):
    humans = [make_user(role.name, role) for role in Role]
    lobby = await start_room(service, humans)
    game = lobby.game
    operative, tile, _ = prepare_terminal_guess(game, "red", "own")
    await game.guess_tile(operative, tile)

    await service.leave_lobby(humans[0], str(lobby.id))

    assert game.state.check_win() == "red"
    assert len(game.state.users) == 3
    assert all(user.is_human for user in game.state.users)
    assert not game._tasks


async def test_human_can_retry_a_failed_ai_clue_and_resume_the_game(service, tasks):
    owner = make_user("Owner", Role.BLUE_SPYMASTER)
    operative = make_user("Human operative", Role.RED_OPERATIVE)
    with capture_game_tasks(tasks):
        lobby = await start_room(service, [owner, operative])
    game = lobby.game
    game.ai.provide_clue.side_effect = [RuntimeError("temporary failure"), ("RECOVERED", 1)]
    await asyncio.wait_for(asyncio.gather(*tasks), timeout=2)
    assert game.ai_error is not None
    assert game.state.current_turn == Role.RED_SPYMASTER

    with capture_game_tasks(tasks):
        await MessageRouter(service).route_message(context_for(owner, lobby), "retryAI", {
            "gameId": game.state.id, "turnId": game.state.turn_id,
        })
    await asyncio.wait_for(asyncio.gather(*tasks), timeout=2)

    assert game.ai_error is None
    assert game.state.clue == ("RECOVERED", 1)
    assert game.state.get_on_turn_user() is operative
    game.ai.provide_clue.assert_awaited()
    assert game.ai.provide_clue.await_count == 2


async def test_command_from_an_earlier_matching_role_turn_is_rejected(make_game, service):
    game = await make_game()
    owner = game.state.get_on_turn_user()
    lobby = await service.create_lobby(owner, "Turn versions")
    lobby.game = game
    stale = {"gameId": game.state.id, "turnId": game.state.turn_id, "word": "OLD", "number": 1}
    await game.provide_clue(owner, "RED", 1)
    await game.pass_turn(game.state.get_on_turn_user())
    await game.provide_clue(game.state.get_on_turn_user(), "BLUE", 1)
    await game.pass_turn(game.state.get_on_turn_user())
    assert game.state.get_on_turn_user() is owner
    before = game.get_state_update(owner, False)

    response = await MessageRouter(service).route_message(context_for(owner, lobby), "provideClue", stale)

    assert response["serverMessageType"] == "error"
    assert game.get_state_update(owner, False) == before


async def test_join_revalidates_capacity_after_waiting_for_old_lobby_cleanup(service, tasks):
    moving = make_user("Moving", Role.RED_SPYMASTER)
    remaining = make_user("Remaining", Role.BLUE_SPYMASTER)
    old = await start_room(service, [moving, remaining])
    for tile in old.game.state.tiles:
        if tile.team == "red":
            tile.reveal()
    destination = await service.create_lobby(make_user("Destination owner"), "Destination")
    for name in ("Second", "Third"):
        await service.join_lobby(make_user(name), str(destination.id))
    sending, release = asyncio.Event(), asyncio.Event()

    async def hold_cleanup(message):
        sending.set()
        await release.wait()

    connection_for(remaining).send.side_effect = hold_cleanup
    context = context_for(moving, old)
    task = asyncio.create_task(MessageRouter(service).route_message(
        context, "joinLobby", {"lobbyId": str(destination.id)}
    ))
    tasks.append(task)
    await checkpoint(sending)
    assert await service.join_lobby(make_user("Last slot"), str(destination.id)) is destination
    release.set()
    response = await asyncio.wait_for(task, timeout=2)

    assert len(destination.users) == 4
    assert moving not in destination.users
    assert context.lobby_id is None
    assert response["serverMessageType"] == "error"


async def test_explicit_leave_retires_a_finished_room_and_is_idempotent(service):
    owner = make_user("Owner", Role.RED_SPYMASTER)
    lobby = await start_room(service, [owner])
    for tile in lobby.game.state.tiles:
        if tile.team == "red":
            tile.reveal()
    context = context_for(owner, lobby)
    router = MessageRouter(service)

    assert await router.route_message(context, "leaveLobby", {}) == {"serverMessageType": "lobbyLeft"}
    assert context.lobby_id is None
    assert service.get_lobby(str(lobby.id)) is None
    assert lobby.game.disposed
    assert context.lobby_id is None and not owner.is_ready and owner.role is None
    assert await router.route_message(context, "leaveLobby", {}) == {"serverMessageType": "lobbyLeft"}


async def test_ai_takeover_during_startup_is_scheduled_when_activation_completes(service, tasks):
    departing = make_user("Departing", Role.RED_SPYMASTER)
    remaining = make_user("Remaining", Role.RED_OPERATIVE)
    lobby = await service.create_lobby(departing, "Startup takeover")
    await service.join_lobby(remaining, str(lobby.id))
    sending, release = asyncio.Event(), asyncio.Event()

    async def hold_startup(message):
        sending.set()
        await release.wait()

    connection_for(departing).send.side_effect = hold_startup
    startup = asyncio.create_task(service.start_game(lobby))
    tasks.append(startup)
    await checkpoint(sending)
    game = lobby.game
    assert not game.started
    game.ai.provide_clue.return_value = ("STARTUP", 1)

    await service.leave_lobby(departing, str(lobby.id))
    assert not game.state.get_on_turn_user().is_human
    with capture_game_tasks(tasks):
        release.set()
        await asyncio.wait_for(startup, timeout=2)
    await asyncio.wait_for(asyncio.gather(*tasks), timeout=2)

    assert game.started
    game.ai.provide_clue.assert_awaited_once()
    assert game.state.get_on_turn_user() is remaining
    assert game.state.clue == ("STARTUP", 1)


async def test_waiting_room_starts_when_the_only_unready_human_leaves(service):
    ready = make_user("Ready", Role.RED_SPYMASTER)
    ready.is_ready = True
    unready = make_user("Unready", Role.BLUE_SPYMASTER)
    lobby = await service.create_lobby(ready, "Ready after departure")
    await service.join_lobby(unready, str(lobby.id))
    assert lobby.game is None

    await service.leave_lobby(unready, str(lobby.id))

    assert lobby.game is not None
    assert lobby.game.started
    assert lobby.game.state.get_on_turn_user() is ready
