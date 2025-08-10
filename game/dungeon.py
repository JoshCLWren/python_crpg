from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional
import json
import random



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
    def __init__(
        self,
        grid: Optional[List[List[Tile]]] = None,
        *,
        procedural: bool = True,
        width: int = 31,
        height: int = 31,
        seed: Optional[int] = None,
    ) -> None:
        # Choose source of map: provided grid, procedural, or default static map
        if grid is not None:
            self.grid = grid
        elif procedural:
            self.grid = generate_maze(width, height, seed=seed)
        else:
            self.grid = default_map()

        # Place player in a walkable cell facing east
        # Prefer (1,1) if walkable; else find first walkable tile
        if not self.is_wall(1, 1):
            start_x, start_y = 1, 1
        else:
            start_x, start_y = self._find_first_floor()
        self.player = PlayerState(x=start_x, y=start_y, facing=1)
        # Track visited tiles (for map view)
        self.visited: List[List[bool]] = [
            [False for _ in range(len(self.grid[0]))] for _ in range(len(self.grid))
        ]
        # Mark starting position as visited
        self._mark_visited(self.player.x, self.player.y)

    # --- Persistence ---
    def to_dict(self) -> dict:
        return {
            "grid": self.grid,
            "player": {
                "x": self.player.x,
                "y": self.player.y,
                "facing": self.player.facing,
            },
            "visited": self.visited,
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
        # Load visited if present; otherwise initialize and mark current position
        visited = data.get("visited")
        if isinstance(visited, list) and visited and isinstance(visited[0], list):
            # Ensure dimensions match the grid; if not, rebuild
            if len(visited) == len(self.grid) and all(len(row) == len(self.grid[0]) for row in visited):
                self.visited = visited  # type: ignore[assignment]
            else:
                self.visited = [
                    [False for _ in range(len(self.grid[0]))] for _ in range(len(self.grid))
                ]
        else:
            self.visited = [
                [False for _ in range(len(self.grid[0]))] for _ in range(len(self.grid))
            ]
        self._mark_visited(self.player.x, self.player.y)

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
            self._mark_visited(self.player.x, self.player.y)

    def step_back(self) -> None:
        dx, dy = self._dir_vec()
        nx, ny = self.player.x - dx, self.player.y - dy
        if not self.is_wall(nx, ny):
            self.player.x, self.player.y = nx, ny
            self._mark_visited(self.player.x, self.player.y)

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

    # --- Visited helpers ---
    def _mark_visited(self, x: int, y: int) -> None:
        if 0 <= y < len(self.visited) and 0 <= x < len(self.visited[0]):
            # Only mark walkable tiles
            if not self.is_wall(x, y):
                self.visited[y][x] = True

    def _find_first_floor(self) -> tuple[int, int]:
        for y in range(len(self.grid)):
            for x in range(len(self.grid[0])):
                if not self.is_wall(x, y):
                    return x, y
        # Fallback to (0,0) if somehow all walls
        return 0, 0


def generate_maze(width: int, height: int, *, seed: Optional[int] = None) -> List[List[Tile]]:
    """Generate a perfect maze using DFS backtracking.

    - 1 = wall, 0 = floor
    - Guarantees outer border walls and full connectivity among floor cells.
    - Works best with odd dimensions; even sizes are adjusted down by 1.
    """
    rng = random.Random(seed)

    # Ensure odd dimensions >= 5
    w = max(5, width - (width + 1) % 2)  # make odd
    h = max(5, height - (height + 1) % 2)  # make odd

    # Start with all walls
    grid: List[List[Tile]] = [[1 for _ in range(w)] for _ in range(h)]

    # Helper to carve a cell
    def carve(x: int, y: int) -> None:
        grid[y][x] = 0

    # Directions: N, S, W, E as 2-step moves (carve between)
    dirs = [(0, -2), (0, 2), (-2, 0), (2, 0)]

    # Pick a random starting cell at odd coordinates
    sx = rng.randrange(1, w, 2)
    sy = rng.randrange(1, h, 2)
    carve(sx, sy)

    stack: list[tuple[int, int]] = [(sx, sy)]
    while stack:
        x, y = stack[-1]
        # Shuffle directions per step for randomness
        rng.shuffle(dirs)
        carved = False
        for dx, dy in dirs:
            nx, ny = x + dx, y + dy
            bx, by = x + dx // 2, y + dy // 2  # between cell (wall to break)
            if 1 <= nx < w - 1 and 1 <= ny < h - 1 and grid[ny][nx] == 1:
                # If target cell is a wall and inside bounds, carve passage
                grid[by][bx] = 0
                grid[ny][nx] = 0
                stack.append((nx, ny))
                carved = True
                break
        if not carved:
            stack.pop()

    # Ensure (1,1) is floor and outer border remains walls
    carve(1, 1)
    for ix in range(w):
        grid[0][ix] = 1
        grid[h - 1][ix] = 1
    for iy in range(h):
        grid[iy][0] = 1
        grid[iy][w - 1] = 1

    return grid
