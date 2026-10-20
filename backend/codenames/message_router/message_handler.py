from typing import Dict, Protocol, Any, Optional

from codenames.services.connection_service import UserContext


class MessageHandler(Protocol):
    """Protocol for handling different message types"""
    async def handle(self, user_context: 'UserContext', data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        ...
