from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import List, Optional, Literal, Dict, Any
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
    hp: int = 10
    gold: int = 0
    base_atk: int = 1
    weapon: Optional[str] = None
    weapon_atk: int = 0

    @property
    def atk(self) -> int:
        return self.base_atk + (self.weapon_atk or 0)


ItemKind = Literal["gold", "weapon"]


@dataclass
class Item:
    x: int
    y: int
    kind: ItemKind
    amount: int = 0           # for gold
    name: Optional[str] = None  # for weapon name
    atk: int = 0              # for weapon attack bonus


@dataclass
class Monster:
    x: int
    y: int
    name: str
    hp: int
    atk: int


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

        # Entities
        self.items: List[Item] = []
        self.monsters: List[Monster] = []
        self._messages: List[str] = []

        # Populate world with a few items/monsters
        self._rng = random.Random(seed if seed is not None else 1337)
        self._populate_entities()

    # --- Persistence ---
    def to_dict(self) -> dict:
        return {
            "grid": self.grid,
            "player": {
                "x": self.player.x,
                "y": self.player.y,
                "facing": self.player.facing,
                "hp": self.player.hp,
                "gold": self.player.gold,
                "base_atk": self.player.base_atk,
                "weapon": self.player.weapon,
                "weapon_atk": self.player.weapon_atk,
            },
            "visited": self.visited,
            "items": [asdict(it) for it in self.items],
            "monsters": [asdict(m) for m in self.monsters],
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
            hp=int(player.get("hp", self.player.hp)),
            gold=int(player.get("gold", self.player.gold)),
            base_atk=int(player.get("base_atk", self.player.base_atk)),
            weapon=player.get("weapon", self.player.weapon),
            weapon_atk=int(player.get("weapon_atk", self.player.weapon_atk)),
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

        # Load entities if present
        items = data.get("items", [])
        monsters = data.get("monsters", [])
        self.items = []
        self.monsters = []
        if isinstance(items, list):
            for it in items:
                try:
                    self.items.append(
                        Item(
                            x=int(it.get("x")),
                            y=int(it.get("y")),
                            kind=str(it.get("kind")),
                            amount=int(it.get("amount", 0)),
                            name=it.get("name"),
                            atk=int(it.get("atk", 0)),
                        )
                    )
                except Exception:
                    continue
        if isinstance(monsters, list):
            for mo in monsters:
                try:
                    self.monsters.append(
                        Monster(
                            x=int(mo.get("x")),
                            y=int(mo.get("y")),
                            name=str(mo.get("name", "Goblin")),
                            hp=int(mo.get("hp", 3)),
                            atk=int(mo.get("atk", 1)),
                        )
                    )
                except Exception:
                    continue

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
        if self._try_combat(nx, ny):
            return
        if not self.is_wall(nx, ny):
            self.player.x, self.player.y = nx, ny
            self._mark_visited(self.player.x, self.player.y)
            self._on_enter(nx, ny)

    def step_back(self) -> None:
        dx, dy = self._dir_vec()
        nx, ny = self.player.x - dx, self.player.y - dy
        if self._try_combat(nx, ny):
            return
        if not self.is_wall(nx, ny):
            self.player.x, self.player.y = nx, ny
            self._mark_visited(self.player.x, self.player.y)
            self._on_enter(nx, ny)

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

    # --- Entity helpers ---
    def _populate_entities(self) -> None:
        # Collect all floor tiles
        floors: list[tuple[int, int]] = [
            (x, y)
            for y in range(len(self.grid))
            for x in range(len(self.grid[0]))
            if not self.is_wall(x, y) and not (x == self.player.x and y == self.player.y)
        ]
        self._rng.shuffle(floors)
        # Place some gold piles
        for _ in range(min(8, len(floors))):
            if not floors:
                break
            x, y = floors.pop()
            amt = self._rng.randint(5, 25)
            self.items.append(Item(x=x, y=y, kind="gold", amount=amt))
        # Place a few weapons
        weapons = [
            ("Dagger", 1),
            ("Shortsword", 2),
            ("Axe", 3),
        ]
        for _ in range(min(3, len(floors))):
            if not floors:
                break
            x, y = floors.pop()
            name, atk = self._rng.choice(weapons)
            self.items.append(Item(x=x, y=y, kind="weapon", name=name, atk=atk))
        # Place some monsters
        names = ["Rat", "Goblin", "Skeleton", "Bat"]
        # Increase density: target ~20% of remaining floor tiles, at least 10
        target = max(10, len(floors) // 5)
        count = min(target, len(floors))
        for _ in range(count):
            if not floors:
                break
            x, y = floors.pop()
            name = self._rng.choice(names)
            hp = self._rng.randint(2, 6)
            atk = self._rng.randint(1, 3)
            self.monsters.append(Monster(x=x, y=y, name=name, hp=hp, atk=atk))

    def _monster_at(self, x: int, y: int) -> Optional[Monster]:
        for m in self.monsters:
            if m.x == x and m.y == y:
                return m
        return None

    def _item_at(self, x: int, y: int) -> Optional[Item]:
        for it in self.items:
            if it.x == x and it.y == y:
                return it
        return None

    def _try_combat(self, nx: int, ny: int) -> bool:
        m = self._monster_at(nx, ny)
        if m is None:
            return False
        # Attack monster
        m.hp -= max(0, self.player.atk)
        if m.hp <= 0:
            self._messages.append(f"You defeated the {m.name}!")
            # Move into the tile after defeating
            self.monsters.remove(m)
            self.player.x, self.player.y = nx, ny
            self._mark_visited(self.player.x, self.player.y)
            self._on_enter(nx, ny)
        else:
            # Monster retaliates
            self.player.hp -= max(0, m.atk)
            self._messages.append(f"You hit the {m.name} ({m.hp} hp left). It hits you (-{m.atk} hp).")
            if self.player.hp <= 0:
                self._messages.append("You have fallen...")
        return True

    def _on_enter(self, x: int, y: int) -> None:
        it = self._item_at(x, y)
        if not it:
            return
        if it.kind == "gold":
            self.player.gold += max(0, it.amount)
            self._messages.append(f"Picked up {it.amount} gold.")
            self.items.remove(it)
        elif it.kind == "weapon":
            new_atk = max(0, it.atk)
            if self.player.weapon is None or new_atk > (self.player.weapon_atk or 0):
                self.player.weapon = it.name or "Weapon"
                self.player.weapon_atk = new_atk
                self._messages.append(f"Equipped {self.player.weapon} (+{new_atk} atk).")
            else:
                self._messages.append(f"Found {it.name or 'weapon'} (+{new_atk}), but kept current.")
            self.items.remove(it)

    # --- Messaging ---
    def drain_messages(self) -> List[str]:
        msgs = self._messages[:]
        self._messages.clear()
        return msgs

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


def generate_long_corridor(length: int = 101, height: int = 9) -> List[List[Tile]]:
    """Generate a long straight corridor for testing the renderer.

    - The corridor runs East-West along the center row.
    - All outer borders are walls; only the center row from x=1..length-2 is floor.
    - Length is clamped to >= 7 and made odd; height is clamped to >= 5 and made odd.
    """
    # Validate and normalize dimensions
    if length < 7:
        length = 7
    if height < 5:
        height = 5
    # Make odd for symmetry
    if length % 2 == 0:
        length -= 1
    if height % 2 == 0:
        height -= 1

    grid: List[List[Tile]] = [[1 for _ in range(length)] for _ in range(height)]
    mid = height // 2
    for x in range(1, length - 1):
        grid[mid][x] = 0
    # keep outer border as walls
    return grid
