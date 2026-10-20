"""Basic room operations and nonblocking AI execution."""

import asyncio

from codenames.message_router.message_router import MessageRouter
from codenames.model import Role
from tests.helpers import context_for, make_service, make_user


async def test_lobby_creation_and_user_joining():
    service = make_service()
    user = make_user("Test User")
    lobby = await service.create_lobby(user, "Test Lobby")
    assert lobby.name == "Test Lobby"
    assert lobby.users == [user]
    assert context_for(user).lobby_id == lobby.id
    assert lobby.get_player_update()["players"][0]["inLobby"]
    other = make_user("User 2")
    assert await service.join_lobby(other, lobby.id) is lobby
    assert lobby.users == [user, other]


async def test_message_routing_and_lobby_handlers():
    service = make_service()
    user = make_user()
    context = context_for(user)
    router = MessageRouter(service)
    assert await router.route_message(context, "idRequest", {}) == {
        "serverMessageType": "idAssign", "uuid": user.id,
    }
    result = await router.route_message(context, "createLobby", {"name": "Test Lobby"})
    assert result["lobbyId"] == context.lobby_id
    assert (await service.get_lobby(context.lobby_id)).name == "Test Lobby"


async def test_human_input_not_buffered_during_ai_turns():
    service = make_service()
    human = make_user("Human Red Guesser", Role.RED_OPERATIVE)
    lobby = await service.create_lobby(human, "Buffering test")
    requested, release = asyncio.Event(), asyncio.Event()

    async def held_clue(*args):
        requested.set()
        await release.wait()
        return "TESTCLUE", 1

    service.ai_factory.return_value.provide_clue.side_effect = held_clue
    await service.start_game(lobby)
    try:
        await asyncio.wait_for(requested.wait(), 2)
        # The API loop remains available while the separate AI task is suspended.
        response = await asyncio.wait_for(MessageRouter(service).route_message(
            context_for(human), "guessTile", {"word": lobby.game.state.tiles[0].word},
        ), 1)
        assert response["serverMessageType"] == "error"
        assert response["message"] == "It is not your operative turn"
        assert not any(tile.revealed for tile in lobby.game.state.tiles)
    finally:
        release.set()
        await lobby.game.dispose()


async def test_ai_actions_execute_asynchronously_without_blocking():
    service = make_service()
    human = make_user("Blue spymaster", Role.BLUE_SPYMASTER)
    lobby = await service.create_lobby(human, "Chain reaction")
    requested, release = asyncio.Event(), asyncio.Event()

    async def held_clue(*args):
        requested.set()
        await release.wait()
        return "CHAIN", 1

    service.ai_factory.return_value.provide_clue.side_effect = held_clue
    try:
        await asyncio.wait_for(service.start_game(lobby), 1)
        await asyncio.wait_for(requested.wait(), 2)
        assert lobby.game.started
        assert not release.is_set()
    finally:
        release.set()
        await lobby.game.dispose()
