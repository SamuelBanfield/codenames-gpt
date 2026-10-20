"""Waiting-room state and pure projections; lifecycle operations live in LobbyService."""

import uuid
from typing import Optional

from codenames.game.runtime import GameRuntime
from codenames.model import User


class Lobby:
    def __init__(self, user: User, name: str):
        self.id = str(uuid.uuid4())
        self.name = name
        self.lobby_owner = user
        self.users = [user]
        self.revision = 1
        self.game: Optional[GameRuntime] = None

    def ready_to_start(self) -> bool:
        return self.game is None and bool(self.users) and all(
            user.name and user.role is not None and user.is_ready for user in self.users
        )

    def to_json(self) -> dict:
        return {"name": self.name, "id": self.id, "players": len(self.users), "game": self.game is not None}

    def get_player_update(self) -> dict:
        participants = self.game.state.users if self.game else []
        return {
            "serverMessageType": "playerUpdate",
            "players": [user.to_json(in_lobby=True, in_game=user in participants) for user in self.users],
            "lobbyId": self.id,
            "lobbyRevision": self.revision,
        }
