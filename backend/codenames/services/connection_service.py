from typing import Dict, Any, Optional
from abc import ABC, abstractmethod
import logging
import uuid

logger = logging.getLogger(__name__)

class Connection(ABC):
    """Abstract connection interface"""
    
    def __init__(self):
        self.id = str(uuid.uuid4())
    
    @abstractmethod
    async def send_message(self, message: Dict[str, Any]) -> None:
        pass
    
    @abstractmethod
    async def close(self) -> None:
        pass

class ConnectionManager:
    """Manages active connections"""
    
    def __init__(self):
        self._connections: Dict[str, Connection] = {}
    
    def add_connection(self, connection: Connection) -> str:
        """Add a new connection and return its ID"""
        self._connections[connection.id] = connection
        logger.info(f"Added connection {connection.id}")
        return connection.id
    
    def remove_connection(self, connection_id: str) -> Optional[Connection]:
        """Remove and return a connection"""
        connection = self._connections.pop(connection_id, None)
        if connection:
            logger.info(f"Removed connection {connection_id}")
        return connection
    
    def get_connection(self, connection_id: str) -> Optional[Connection]:
        """Get a connection by ID"""
        return self._connections.get(connection_id)
    
    async def broadcast_to_connections(self, connection_ids: list[str], message: Dict[str, Any]) -> None:
        """Send a message to multiple connections"""
        for conn_id in connection_ids:
            connection = self.get_connection(conn_id)
            if connection:
                try:
                    await connection.send_message(message)
                except Exception as e:
                    logger.error(f"Failed to send message to {conn_id}: {e}")
    
    async def close_all_connections(self) -> None:
        """Close all connections"""
        for connection in self._connections.values():
            try:
                await connection.close()
            except Exception as e:
                logger.error(f"Error closing connection {connection.id}: {e}")
        self._connections.clear()
