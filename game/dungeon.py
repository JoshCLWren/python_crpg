from __future__ import annotations

from dataclasses import dataclass
from typing import List
import json



Tile = int  # 0=floor, 1=wall


def default_map() -> List[List[Tile]]:
    # Simple dungeon: outer walls with corridors and a room.
    layout = [
        "################",
        "#......#.......#",
        "#.####.#.#####.#",
        "#.#  #.#.#   #.#",
        "#.#  #...#   #.#",
        "#.#  #####   #.#",
        "#.#          #.#",
        "#.#   ###### #.#",
        "#.#   #    # #.#",
        "#.#   # ## # #.#",
        "#.#   # ## # #.#",
        "#.#   #    # #.#",
        "#.#   ###### #.#",
        "#.#          #.#",
        "#..............#",
        "################",
    ]
    # Replace spaces with floor for readability in the string map
    layout = [row.replace(" ", ".") for row in layout]
    grid: List[List[Tile]] = [[1 if c == "#" else 0 for c in row] for row in layout]
    return grid


@dataclass
class PlayerState:
    x: int
    y: int
    facing: int  # 0=N, 1=E, 2=S, 3=W


class Dungeon:
    def __init__(self, grid: List[List[Tile]] | None = None) -> None:
        self.grid = grid if grid is not None else default_map()
        # Place player in a walkable cell facing north
        self.player = PlayerState(x=2, y=2, facing=1)

    # --- Persistence ---
    def to_dict(self) -> dict:
        return {
            "grid": self.grid,
            "player": {
                "x": self.player.x,
                "y": self.player.y,
                "facing": self.player.facing,
            },
        }

    def load_dict(self, data: dict) -> None:
        grid = data.get("grid")
        player = data.get("player", {})
        if isinstance(grid, list):
            self.grid = grid  # type: ignore[assignment]
        self.player = PlayerState(
            x=int(player.get("x", self.player.x)),
            y=int(player.get("y", self.player.y)),
            facing=int(player.get("facing", self.player.facing)),
        )

    def save_to_file(self, path: str) -> None:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f)

    def load_from_file(self, path: str) -> None:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.load_dict(data)

    # --- Queries ---
    def is_wall(self, x: int, y: int) -> bool:
        if y < 0 or y >= len(self.grid) or x < 0 or x >= len(self.grid[0]):
            return True
        return self.grid[y][x] == 1

    # --- Movement ---
    def turn_left(self) -> None:
        self.player.facing = (self.player.facing - 1) % 4

    def turn_right(self) -> None:
        self.player.facing = (self.player.facing + 1) % 4

    def step_forward(self) -> None:
        dx, dy = self._dir_vec()
        nx, ny = self.player.x + dx, self.player.y + dy
        if not self.is_wall(nx, ny):
            self.player.x, self.player.y = nx, ny

    def step_back(self) -> None:
        dx, dy = self._dir_vec()
        nx, ny = self.player.x - dx, self.player.y - dy
        if not self.is_wall(nx, ny):
            self.player.x, self.player.y = nx, ny

    # --- Utils ---
    def _dir_vec(self) -> tuple[int, int]:
        f = self.player.facing
        if f == 0:  # N
            return (0, -1)
        if f == 1:  # E
            return (1, 0)
        if f == 2:  # S
            return (0, 1)
        return (-1, 0)  # W

    def transform_local(self, forward: int, right: int) -> tuple[int, int]:
        # Convert local camera-space (forward,right) offsets to world (x,y)
        px, py, f = self.player.x, self.player.y, self.player.facing
        if f == 0:  # N
            return (px + right, py - forward)
        if f == 1:  # E
            return (px + forward, py + right)
        if f == 2:  # S
            return (px - right, py + forward)
        # W
        return (px - forward, py - right)
