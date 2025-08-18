
from typing import List

from codenames.model import Tile


def get_tile_by_word(word: str, tiles: List[Tile]) -> Tile:
    for tile in tiles:
        if tile.word.replace(" ", "").lower() == word.replace(" ", "").lower():
            return tile
    raise ValueError(f"No tile found for word {word}")
