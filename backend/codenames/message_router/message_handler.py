from typing import Dict, Protocol, Any, Optional


class MessageHandler(Protocol):
    """Protocol for handling different message types"""
    async def handle(self, user_context: 'UserContext', data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        ...

class UserContext:
    """Context for a user session"""
    def __init__(self, user, connection_id: str):
        self.user = user
        self.connection_id = connection_id
        self.lobby_id: Optional[str] = None
    
    def join_lobby(self, lobby_id: str) -> None:
        self.lobby_id = lobby_id
    
    def leave_lobby(self) -> None:
        self.lobby_id = None
