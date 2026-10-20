"""Human sessions and bounded transport delivery. AI has no connection."""

import asyncio
import logging
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Callable, Iterable, Optional

from codenames.model import User

logger = logging.getLogger(__name__)


class Connection(ABC):
    def __init__(self, connection_id: Optional[str] = None):
        self.id = connection_id or str(uuid.uuid4())

    @abstractmethod
    async def send(self, message: dict) -> None:
        ...

@dataclass
class UserContext:
    user: User
    connection: Connection
    lobby_id: Optional[str] = None
    send_lock: asyncio.Lock = field(default_factory=asyncio.Lock, repr=False)

    @property
    def connection_id(self) -> str:
        return self.connection.id


class ConnectionManager:
    def __init__(self, send_timeout: float = 5):
        self._sessions: dict[str, UserContext] = {}
        self.send_timeout = send_timeout

    def add_session(self, user: User, connection: Connection) -> UserContext:
        if user.id in self._sessions:
            raise ValueError("User already has a connection")
        context = UserContext(user, connection)
        self._sessions[user.id] = context
        return context

    def get_session(self, user_id: str) -> Optional[UserContext]:
        return self._sessions.get(user_id)

    def remove_session(self, user_id: str) -> None:
        self._sessions.pop(user_id, None)

    async def send(self, user_id: str, message: dict) -> bool:
        session = self.get_session(user_id)
        if session is None:
            return False

        async def deliver():
            async with session.send_lock:
                await session.connection.send(message)

        try:
            await asyncio.wait_for(deliver(), timeout=self.send_timeout)
            return True
        except Exception:
            logger.warning("Delivery failed for connection %s", session.connection_id, exc_info=True)
            return False

    async def broadcast(self, users: Iterable[User], snapshot: Callable[[User], dict]) -> None:
        # Freeze recipient-specific projections before the first suspension.
        messages = [(user.id, snapshot(user)) for user in users if user.is_human]
        await asyncio.gather(*(self.send(user_id, message) for user_id, message in messages))
