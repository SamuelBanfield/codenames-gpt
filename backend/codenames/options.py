"""Explicit startup configuration; importing this module has no side effects."""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping, Optional

from dotenv import dotenv_values

DEFAULT_ENV_FILE = Path(__file__).resolve().parent.parent / ".env"


@dataclass(frozen=True)
class Settings:
    host: str
    websocket_port: int
    openai_api_key: str = field(repr=False)
    gpt_model: str
    guess_delay: int


def load_settings(*, env_file: Optional[Path] = DEFAULT_ENV_FILE,
                  environ: Optional[Mapping[str, str]] = None) -> Settings:
    values = dict(dotenv_values(env_file, interpolate=False)) if env_file is not None else {}
    values.update(os.environ if environ is None else environ)

    def text(name, default=None):
        value = values.get(name, default)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{name} must be a nonempty value")
        return value.strip()

    def integer(name, default, minimum, maximum=None):
        try:
            value = int(text(name, default))
        except ValueError:
            raise ValueError(f"{name} must be an integer") from None
        if value < minimum or (maximum is not None and value > maximum):
            bounds = f"between {minimum} and {maximum}" if maximum is not None else f"at least {minimum}"
            raise ValueError(f"{name} must be {bounds}")
        return value

    return Settings(
        host=text("HOST", "0.0.0.0"),
        websocket_port=integer("WEBSOCKET_PORT", "8000", 1, 65535),
        openai_api_key=text("OPENAI_API_KEY"),
        gpt_model=text("GPT_MODEL", "gpt-4o"),
        guess_delay=integer("GUESS_DELAY", "0", 0),
    )
