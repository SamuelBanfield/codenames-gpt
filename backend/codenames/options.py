import json
import logging
import os
import pathlib

_properties_file_path = pathlib.Path(__file__).parent.parent / ".properties.json"

_properties = {}
try:
    with open(_properties_file_path) as property_file:
        _properties = json.load(property_file)
except FileNotFoundError:
    logging.warning(f".properties.json file not found at {_properties_file_path}, relying on environment variables only")
    pass

HOST = os.getenv("HOST", _properties.get("host", "0.0.0.0")) 
WEBSOCKET_PORT = int(os.getenv("WEBSOCKET_PORT", _properties.get("websocketPort", 8000)))
OPEN_AI_KEY = os.getenv("OPENAI_KEY", _properties.get("openaiKey"))
GPT_MODEL: str = os.getenv("GPT_MODEL", _properties.get("gptModel", "gpt-4o"))
GUESS_DELAY = int(os.getenv("GUESS_DELAY", _properties.get("guessDelay", 0)))

# Validate required properties
if not OPEN_AI_KEY:
    raise ValueError("OPENAI_KEY must be set via environment variable or .properties.json")
