"""Explicit configuration, composition, and whole-application resource lifetime."""

import asyncio
import os
from pathlib import Path
import subprocess
import sys
from unittest.mock import AsyncMock, Mock

import pytest

from codenames import app
from codenames.gpt.chat_gpt import ChatGPT
from codenames.model import Role
from codenames.options import Settings, load_settings
from tests.helpers import connection_for, context_for, make_service, make_user


def configured(**overrides):
    values = dict(host="127.0.0.1", websocket_port=8000, openai_api_key="test-only-key",
                  gpt_model="configured-model", guess_delay=3)
    values.update(overrides)
    return Settings(**values)


def test_settings_defaults_without_dotenv_or_process_environment():
    settings = load_settings(env_file=None, environ={"OPENAI_API_KEY": "test-key"})
    assert settings.host == "0.0.0.0"
    assert settings.websocket_port == 8000
    assert settings.gpt_model == "gpt-4o"
    assert settings.guess_delay == 0
    assert "test-key" not in repr(settings)


def test_dotenv_precedence_and_no_process_environment_mutation(tmp_path, monkeypatch):
    path = tmp_path / ".env"
    path.write_text("OPENAI_API_KEY='file-key'\nHOST=localhost\nWEBSOCKET_PORT=8123\n"
                    "GPT_MODEL=file-model\nGUESS_DELAY=4\n", encoding="utf-8")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    settings = load_settings(env_file=path, environ={"GPT_MODEL": "env-model", "WEBSOCKET_PORT": "9000"})
    assert settings.openai_api_key == "file-key"
    assert settings.host == "localhost"
    assert settings.websocket_port == 9000
    assert settings.gpt_model == "env-model"
    assert settings.guess_delay == 4
    assert "OPENAI_API_KEY" not in os.environ


@pytest.mark.parametrize("name,value", [
    ("OPENAI_API_KEY", ""), ("HOST", " "), ("GPT_MODEL", ""),
    ("WEBSOCKET_PORT", "not-a-number-secret"), ("WEBSOCKET_PORT", "0"),
    ("WEBSOCKET_PORT", "65536"), ("GUESS_DELAY", "-1"), ("GUESS_DELAY", "1.5"),
])
def test_invalid_settings_report_field_without_echoing_value(name, value):
    with pytest.raises(ValueError, match=name) as error:
        load_settings(env_file=None, environ={"OPENAI_API_KEY": "private-key", name: value})
    assert "private-key" not in str(error.value)
    assert "not-a-number-secret" not in str(error.value)


def test_old_key_name_is_not_a_supported_alias():
    with pytest.raises(ValueError, match="OPENAI_API_KEY"):
        load_settings(env_file=None, environ={"OPENAI_KEY": "old-key"})


def test_default_dotenv_location_is_independent_of_working_directory(tmp_path, monkeypatch):
    from codenames.options import DEFAULT_ENV_FILE
    assert DEFAULT_ENV_FILE == Path(__file__).resolve().parents[1] / ".env"
    monkeypatch.chdir(tmp_path)
    assert DEFAULT_ENV_FILE.is_absolute()


def test_imports_do_not_load_settings_read_dotenv_or_construct_clients():
    # Warm third-party imports first; the assertion concerns application imports,
    # not a library's own import machinery or platform probing.
    script = "\n".join([
        "import importlib, os, pathlib, pkgutil",
        "from unittest.mock import patch",
        "import dotenv, openai, websockets, codenames",
        "os.environ.pop('OPENAI_API_KEY', None)",
        "modules = [item.name for item in pkgutil.walk_packages(codenames.__path__, 'codenames.') ]",
        "with patch('dotenv.dotenv_values', side_effect=AssertionError('configuration read at import')), \\",
        "     patch('openai.AsyncOpenAI', side_effect=AssertionError('client created at import')):",
        "    for name in modules: importlib.import_module(name)",
    ])
    result = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr


async def test_ai_wrapper_uses_explicit_credentials_and_model():
    wrapper = ChatGPT("test-explicit-key", "test-model")
    client = wrapper.client
    client.chat.completions.create = AsyncMock(return_value="response")
    assert await wrapper._get_gpt_response("system", "user") == "response"
    assert client.chat.completions.create.await_args.kwargs["model"] == "test-model"
    client.close = AsyncMock()
    await wrapper.close()
    client.close.assert_awaited_once()


async def test_main_loads_settings_once_and_wires_dependencies_without_creating_ai(monkeypatch):
    settings = configured()
    loader = Mock(return_value=settings)
    wrapper = Mock()
    seen = []

    async def inspect_serve(received_settings, rooms):
        seen.append(rooms)
        assert received_settings is settings
        assert rooms.guess_delay == settings.guess_delay
        wrapper.assert_not_called()
        rooms.ai_factory()
        wrapper.assert_called_once_with(settings.openai_api_key, settings.gpt_model)
        await rooms.shutdown()

    monkeypatch.setattr(app, "load_settings", loader)
    monkeypatch.setattr(app, "ChatGPT", wrapper)
    monkeypatch.setattr(app, "serve", inspect_serve)
    await app.main()
    loader.assert_called_once_with()
    assert len(seen) == 1


async def test_invalid_startup_settings_do_not_bind_or_construct_dependencies(monkeypatch):
    monkeypatch.setattr(app, "load_settings", Mock(side_effect=ValueError("invalid config")))
    connections = Mock()
    serve = AsyncMock()
    monkeypatch.setattr(app, "Connections", connections)
    monkeypatch.setattr(app, "serve", serve)
    with pytest.raises(ValueError, match="invalid config"):
        await app.main()
    connections.assert_not_called()
    serve.assert_not_awaited()


async def test_shutdown_cancels_ai_closes_clients_clears_membership_and_rejects_new_work():
    rooms = make_service()
    user = make_user("Human", Role.RED_SPYMASTER)
    lobby = await rooms.create_lobby(user, "Shutdown")
    await rooms.start_game(lobby)
    game = lobby.game
    requested = asyncio.Event()

    async def pending_guesses(*args):
        requested.set()
        await asyncio.Event().wait()

    game.ai.make_guesses.side_effect = pending_guesses
    client = game.ai
    await game.provide_clue(user, "CLUE", 1)
    await asyncio.wait_for(requested.wait(), 1)
    owned = list(game._tasks)
    await rooms.shutdown()
    await rooms.shutdown()
    assert rooms.list_lobbies() == []
    assert context_for(user).lobby_id is None
    assert user.role is None and not user.is_ready
    assert game.disposed and all(task.done() for task in owned)
    client.close.assert_awaited_once()
    with pytest.raises(ValueError, match="shutting down"):
        await rooms.create_lobby(user, "New")
    with pytest.raises(ValueError, match="shutting down"):
        await rooms.start_game(lobby)


async def test_shutdown_during_roster_delivery_prevents_activation_and_ai():
    rooms = make_service()
    user = make_user("Human", Role.BLUE_SPYMASTER)
    lobby = await rooms.create_lobby(user, "Starting")
    sending, release = asyncio.Event(), asyncio.Event()

    async def held_send(message):
        sending.set()
        await release.wait()

    connection_for(user).send.side_effect = held_send
    startup = asyncio.create_task(rooms.start_game(lobby))
    try:
        await asyncio.wait_for(sending.wait(), 1)
        await rooms.shutdown()
    finally:
        release.set()
        await startup
    assert lobby.game.disposed and not lobby.game.started
    assert rooms.list_lobbies() == []
    rooms.ai_factory.assert_not_called()


async def test_listener_failure_still_disposes_existing_rooms(monkeypatch):
    rooms = make_service()
    user = make_user("Human", Role.RED_SPYMASTER)
    lobby = await rooms.create_lobby(user, "Bind failure")
    await rooms.start_game(lobby)
    monkeypatch.setattr(app.websockets, "serve", AsyncMock(side_effect=OSError("port occupied")))
    with pytest.raises(OSError, match="port occupied"):
        await app.serve(configured(), rooms)
    assert lobby.game.disposed
    assert rooms.list_lobbies() == []


async def test_cancellation_closes_listener_and_finishes_room_shutdown(monkeypatch):
    rooms = make_service()
    user = make_user("Human")
    lobby = await rooms.create_lobby(user, "Waiting")
    user.is_ready = True
    user.role = Role.RED_SPYMASTER
    listening = asyncio.Event()
    listener = Mock()
    listener.wait_closed = AsyncMock()

    async def bind(handler, host, port):
        assert handler.__self__.rooms is rooms
        assert handler.__self__.connections is rooms.connections
        assert host == "127.0.0.1" and port == 8000
        listening.set()
        return listener

    monkeypatch.setattr(app.websockets, "serve", bind)
    task = asyncio.create_task(app.serve(configured(), rooms))
    await asyncio.wait_for(listening.wait(), 1)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    listener.close.assert_called_once()
    listener.wait_closed.assert_awaited_once()
    assert rooms.list_lobbies() == []
    assert lobby.game is None  # Shutdown must not start a ready waiting room.
    assert context_for(user).lobby_id is None


async def test_shutdown_attempts_every_runtime_even_if_one_cleanup_fails():
    rooms = make_service()
    first = await rooms.create_lobby(make_user("First"), "First")
    second = await rooms.create_lobby(make_user("Second"), "Second")
    first.game = Mock(dispose=AsyncMock(side_effect=RuntimeError("cleanup failed")))
    second.game = Mock(dispose=AsyncMock())
    await rooms.shutdown()
    first.game.dispose.assert_awaited_once()
    second.game.dispose.assert_awaited_once()
    assert rooms.list_lobbies() == []
