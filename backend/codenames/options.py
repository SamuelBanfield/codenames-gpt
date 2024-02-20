import json
import pathlib

_properties_file_path = pathlib.Path(__file__).parent.parent / ".properties.json"

try:
    with open(_properties_file_path) as property_file:
        _properties = json.load(property_file)
except FileNotFoundError as e:
    raise FileNotFoundError(f"Could not find .properties.json file: {e}")


HOST = _properties["host"]
WEBSOCKET_PORT = _properties["websocketPort"]
OPEN_AI_KEY = _properties["openaiKey"]
GPT_MODEL = _properties["gptModel"]
GUESS_DELAY = _properties["guessDelay"] if "guessDelay" in _properties else 0 # Optional delay so you can see whats happening