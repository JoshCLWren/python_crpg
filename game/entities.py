from __future__ import annotations

from dataclasses import dataclass
import random


@dataclass
class Creature:
    name: str
    hp: int
    max_hp: int
    min_atk: int
    max_atk: int

    def is_alive(self) -> bool:
        return self.hp > 0

    def attack(self) -> int:
        return random.randint(self.min_atk, self.max_atk)

    def heal(self, amount: int) -> int:
        prev = self.hp
        self.hp = min(self.max_hp, self.hp + amount)
        return self.hp - prev


@dataclass
class Player(Creature):
    potions: int = 1


@dataclass
class Monster(Creature):
    pass

