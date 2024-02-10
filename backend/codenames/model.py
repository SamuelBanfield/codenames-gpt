import json
import pathlib
import random
from typing import List

# WORDS = [
#     "apple", "banana", "carrot", "dog", "elephant",
#     "fox", "grape", "horse", "ice cream", "jellyfish",
#     "kiwi", "lemon", "mango", "nut", "orange",
#     "pear", "quail", "rabbit", "strawberry", "turtle",
#     "unicorn", "violet", "watermelon", "xylophone", "zebra"
#   ]

class CodenamesConnection:

    def send(self, message):
        raise NotImplementedError("Subclasses must implement this method")

class User:

    def __init__(self, name, connection: CodenamesConnection):
        self.name = name

    async def send(self, message):
        print(f"Sending message to {self.name}: {message}")
        await self.connection.send(message)

class Tile:

    def __init__(self, word, team, is_revealed=False):
        self.word = word
        self.revealed = is_revealed
        self.team = team

    def reveal(self):
        self.revealed = True

    def __json__(self):
        return {
            "word": self.word,
            "revealed": self.revealed,
            "team": self.team
        }
    
def _generate_tiles():
    with open(pathlib.Path(__file__).parent 
              / ".." / "wordlist.txt") as f:
        words = f.readlines()
    used_words = random.sample(words, 25)
    red_tiles = [Tile(word.replace("\n", ""), "red") for word in used_words[:9]]
    blue_words = [Tile(word.replace("\n", ""), "blue") for word in used_words[9:17]]
    assassin_word = [Tile(used_words[17].replace("\n", ""), "assassin")]
    neutral_words = [Tile(word.replace("\n", ""), "neutral") for word in used_words[18:25]]
    all_words = red_tiles + blue_words + assassin_word + neutral_words
    random.shuffle(all_words)
    return all_words

class CodenamesGame:

    def __init__(self):
        self.players: List[User] = []
        self.started = False
        self._tiles = _generate_tiles()

    def add_player(self, player: User):
        self.players.append(player)

    def start(self):
        self.started = True

    async def request(self, user: User, message: json):
        if not self.started:
            raise Exception("Game has not started yet")
        if requestType := message["clientMessageType"]:
            if requestType == "tilesRequest":
                await user.send(json.dumps({
                    "serverMessageType": "tilesUpdate",
                    "tiles": [
                        tile.__json__() for tile in self._tiles
                    ]
                }))
            else:
                raise Exception("Unknown request type")
            
        else:
            raise Exception("Unknown request type")
