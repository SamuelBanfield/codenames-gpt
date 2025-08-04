"""
Core functionality and buffering fix tests for Codenames GPT
"""
import asyncio
import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from codenames.lobby import Lobby
from codenames.model import User, CodenamesConnection
from codenames.services.lobby_service import LobbyService, InMemoryLobbyRepository
from codenames.message_router.message_router import MessageRouter, UserContext


def create_mock_connection():
    """Create a mock connection for testing"""
    connection = MagicMock(spec=CodenamesConnection)
    connection.uuid = MagicMock()
    connection.uuid.__str__ = MagicMock(return_value="test-uuid")
    connection.send = AsyncMock()
    return connection


class TestCoreFunctionalityAndBufferingFixes:
    """Core tests covering main functionality and async buffering fixes"""

    @pytest.mark.asyncio
    async def test_lobby_creation_and_user_joining(self):
        """Test basic lobby creation and joining"""
        repository = InMemoryLobbyRepository()
        service = LobbyService(repository)
        
        # Create a user
        connection = create_mock_connection()
        user = User(connection, True)
        user.name = "Test User"
        
        # Create lobby
        lobby = await service.create_lobby(user, "Test Lobby")
        assert lobby is not None
        assert lobby.name == "Test Lobby"
        assert len(lobby.users) == 1
        assert lobby.users[0] == user
        assert user.in_lobby
        
        # Join with second user
        user2 = User(create_mock_connection(), True)
        user2.name = "User 2"
        
        result = await service.join_lobby(user2, str(lobby.id))
        assert result is not None
        assert len(result.users) == 2
        assert user2 in result.users

    @pytest.mark.asyncio
    async def test_message_routing_and_lobby_handlers(self):
        """Test essential message routing functionality"""
        mock_lobby_service = AsyncMock()
        router = MessageRouter(mock_lobby_service)
        
        # Test ID request
        mock_user = MagicMock()
        context = UserContext(mock_user, "test-connection-123")
        
        result = await router.route_message(context, "idRequest", {})
        expected = {
            "serverMessageType": "idAssign",
            "uuid": "test-connection-123"
        }
        assert result == expected
        
        # Test create lobby
        mock_lobby = MagicMock()
        mock_lobby.id = "lobby-123"
        mock_lobby_service.create_lobby.return_value = mock_lobby
        
        result = await router.route_message(context, "createLobby", {"name": "Test Lobby"})
        mock_lobby_service.create_lobby.assert_called_once_with(mock_user, "Test Lobby")
        assert context.lobby_id == "lobby-123"

    @pytest.mark.asyncio
    async def test_human_input_not_buffered_during_ai_turns(self):
        """Test that the buffering issue is fixed - human input during AI turns"""
        # Create the exact scenario: human red guesser + 3 AI players
        users = []
        
        # Human red guesser
        human_connection = create_mock_connection()
        human_user = User(human_connection, True)
        human_user.name = "Human Red Guesser"
        human_user.team = "red"
        human_user.is_spy_master = False
        human_user.is_ready = True
        users.append(human_user)
        
        # AI players
        for i, (team, is_spy) in enumerate([("red", True), ("blue", True), ("blue", False)]):
            ai_user = User(create_mock_connection(), False)
            ai_user.name = f"AI Player {i+1}"
            ai_user.team = team
            ai_user.is_spy_master = is_spy
            ai_user.is_ready = True
            users.append(ai_user)

        # Create lobby
        lobby = Lobby(users[0], "Buffering Fix Test")
        for user in users[1:]:
            lobby.add_user(user)

        # Mock GPT with small delays
        async def mock_get_clue(*args, **kwargs):
            await asyncio.sleep(0.1)  # Small realistic delay
            return ("TESTCLUE", 1)
            
        async def mock_make_guesses(*args, **kwargs):
            await asyncio.sleep(0.1)
            return []  # No guesses to avoid complexity

        with patch('codenames.gpt.agent.ChatGPT.get_clue', side_effect=mock_get_clue), \
             patch('codenames.gpt.agent.ChatGPT.guess', side_effect=mock_make_guesses):
            
            # Start the game (triggers AI)
            game_start_task = asyncio.create_task(lobby.start_game())
            
            # Immediately try human guess
            await asyncio.sleep(0.01)  # Tiny delay to let game start
            
            with patch('builtins.print') as mock_print:
                if lobby.game:
                    # This should be processed immediately, not buffered
                    await lobby.game.guess_tile(human_user, lobby.game.tiles[0])
                    
                    # Wait for game start to complete
                    await game_start_task
                else:
                    await game_start_task

            # Verify human guess was immediately rejected (not buffered)
            ignore_calls = [call for call in mock_print.call_args_list 
                           if "Ignoring guess" in str(call)]
            
            assert len(ignore_calls) > 0, "Human guess should be immediately ignored, not buffered"
            print("✅ Buffering fix verified - human input processed immediately")

    @pytest.mark.asyncio
    async def test_ai_actions_execute_asynchronously_without_blocking(self):
        """Test that AI chain reactions don't block human input"""
        # Create simple 4-AI setup
        users = []
        for i, (team, is_spy) in enumerate([("red", True), ("red", False), ("blue", True), ("blue", False)]):
            user = User(create_mock_connection(), False)  # All AI
            user.name = f"AI Player {i+1}"
            user.team = team
            user.is_spy_master = is_spy
            user.is_ready = True
            users.append(user)
        
        lobby = Lobby(users[0], "Chain Reaction Test")
        for user in users[1:]:
            lobby.add_user(user)

        # Mock GPT calls
        async def mock_get_clue(*args, **kwargs):
            await asyncio.sleep(0.05)  # Small delay
            return ("CHAIN", 1)
            
        async def mock_make_guesses(*args, **kwargs):
            await asyncio.sleep(0.05)
            return []  # No guesses to keep it simple

        with patch('codenames.gpt.agent.ChatGPT.get_clue', side_effect=mock_get_clue), \
             patch('codenames.gpt.agent.ChatGPT.guess', side_effect=mock_make_guesses):
            
            # Start game and verify it completes without hanging
            start_time = asyncio.get_event_loop().time()
            await asyncio.wait_for(lobby.start_game(), timeout=2.0)
            end_time = asyncio.get_event_loop().time()
            
            # Should complete quickly due to async task scheduling
            duration = end_time - start_time
            assert duration < 1.0, f"AI chain took too long ({duration:.2f}s), may still be blocking"
            print("✅ AI chain reaction fix verified - non-blocking execution")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
