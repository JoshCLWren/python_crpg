from __future__ import annotations

import json
import os
import random
from typing import Optional

from .entities import Player, Monster


SAVE_FILE = "savegame.json"


class Game:
    def __init__(self) -> None:
        self.player: Optional[Player] = None
        self.state: str = "menu"  # menu | explore | combat | quit
        self.rooms = [
            "a quiet clearing with soft grass.",
            "a narrow path under towering pines.",
            "a mossy cave entrance that breaths cool air.",
            "an abandoned camp with a smoldering fire.",
            "a rocky outcrop overlooking misty valleys.",
        ]
        self.room_index: int = 0
        self.current_enemy: Optional[Monster] = None

    # --------------- High-level loop ---------------
    def run(self) -> None:
        while self.state != "quit":
            if self.state == "menu":
                self.menu()
            elif self.state == "explore":
                self.explore()
            elif self.state == "combat":
                self.combat()
            else:
                print("Unknown state. Quitting.")
                self.state = "quit"

    # --------------- States ---------------
    def menu(self) -> None:
        print("\n=== CRPG: Whispering Trails ===")
        print("1) New Game")
        print("2) Load Game")
        print("3) Quit")
        choice = input("> ").strip()
        if choice == "1":
            name = input("Enter your name: ").strip() or "Adventurer"
            self.player = Player(name=name, hp=20, max_hp=20, min_atk=2, max_atk=6, potions=2)
            self.room_index = 0
            print(f"Welcome, {self.player.name}.")
            self.state = "explore"
        elif choice == "2":
            if self.load_game():
                print("Game loaded.")
                self.state = "explore"
            else:
                print("No save found or save is corrupt.")
        elif choice == "3":
            self.state = "quit"
        else:
            print("Please choose 1, 2, or 3.")

    def explore(self) -> None:
        assert self.player is not None
        print(f"\nYou are in {self.rooms[self.room_index]}")
        print(f"HP: {self.player.hp}/{self.player.max_hp} | Potions: {self.player.potions}")
        print("Actions: [m]ove, [r]est, [i]nventory, [s]ave, [q]uit")
        cmd = input("> ").strip().lower()

        if cmd in ("m", "move"):
            self.move()
            # Chance for an encounter
            if random.random() < 0.45:
                self.current_enemy = self.spawn_monster()
                print(f"A wild {self.current_enemy.name} appears!")
                self.state = "combat"
        elif cmd in ("r", "rest"):
            healed = self.player.heal(4)
            print(f"You rest and recover {healed} HP.")
        elif cmd in ("i", "inventory"):
            print(f"You have {self.player.potions} potion(s).")
        elif cmd in ("s", "save"):
            if self.save_game():
                print("Game saved.")
            else:
                print("Failed to save.")
        elif cmd in ("q", "quit"):
            print("You decide to end your journey for now.")
            self.state = "quit"
        else:
            print("Unknown action.")

    def combat(self) -> None:
        assert self.player is not None and self.current_enemy is not None
        enemy = self.current_enemy
        player = self.player
        print(f"\n-- Combat: {player.name} vs {enemy.name} --")
        print(f"Your HP: {player.hp}/{player.max_hp} | Enemy HP: {enemy.hp}/{enemy.max_hp}")
        print("Actions: [a]ttack, [p]otion, [r]un")
        cmd = input("> ").strip().lower()

        if cmd in ("a", "attack"):
            dmg = player.attack()
            enemy.hp -= dmg
            print(f"You strike the {enemy.name} for {dmg} damage.")
            if enemy.hp <= 0:
                print(f"The {enemy.name} is defeated!")
                self.current_enemy = None
                self.state = "explore"
                return
            # Enemy retaliates
            edmg = enemy.attack()
            player.hp -= edmg
            print(f"The {enemy.name} hits you for {edmg} damage.")
            if player.hp <= 0:
                print("You fall... Your adventure ends here.")
                self.state = "quit"
        elif cmd in ("p", "potion"):
            if player.potions > 0:
                player.potions -= 1
                healed = player.heal(8)
                print(f"You drink a potion and recover {healed} HP.")
                # Enemy may attack after potion
                if enemy.is_alive():
                    edmg = enemy.attack()
                    player.hp -= edmg
                    print(f"While you recover, {enemy.name} strikes for {edmg}.")
                    if player.hp <= 0:
                        print("You fall... Your adventure ends here.")
                        self.state = "quit"
            else:
                print("You're out of potions!")
        elif cmd in ("r", "run"):
            if random.random() < 0.6:
                print("You manage to escape!")
                self.current_enemy = None
                self.state = "explore"
            else:
                print("You fail to escape!")
                edmg = enemy.attack()
                player.hp -= edmg
                print(f"The {enemy.name} punishes your attempt for {edmg}.")
                if player.hp <= 0:
                    print("You fall... Your adventure ends here.")
                    self.state = "quit"
        else:
            print("Unknown action.")

    # --------------- Helpers ---------------
    def move(self) -> None:
        direction = input("Move [f]orward or [b]ack? ").strip().lower()
        if direction in ("f", "forward"):
            self.room_index = (self.room_index + 1) % len(self.rooms)
            print("You move forward.")
        elif direction in ("b", "back"):
            self.room_index = (self.room_index - 1) % len(self.rooms)
            print("You move back.")
        else:
            print("You stay where you are.")

    def spawn_monster(self) -> Monster:
        names = ["Goblin", "Wolf", "Bandit", "Slime"]
        name = random.choice(names)
        hp = random.randint(6, 12)
        atk_min = random.randint(1, 2)
        atk_max = random.randint(3, 5)
        return Monster(name=name, hp=hp, max_hp=hp, min_atk=atk_min, max_atk=atk_max)

    def save_game(self) -> bool:
        if self.player is None:
            return False
        data = {
            "player": {
                "name": self.player.name,
                "hp": self.player.hp,
                "max_hp": self.player.max_hp,
                "min_atk": self.player.min_atk,
                "max_atk": self.player.max_atk,
                "potions": self.player.potions,
            },
            "room_index": self.room_index,
        }
        try:
            with open(SAVE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f)
            return True
        except OSError:
            return False

    def load_game(self) -> bool:
        if not os.path.exists(SAVE_FILE):
            return False
        try:
            with open(SAVE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            p = data.get("player", {})
            self.player = Player(
                name=p.get("name", "Adventurer"),
                hp=int(p.get("hp", 20)),
                max_hp=int(p.get("max_hp", 20)),
                min_atk=int(p.get("min_atk", 2)),
                max_atk=int(p.get("max_atk", 6)),
                potions=int(p.get("potions", 1)),
            )
            self.room_index = int(data.get("room_index", 0)) % len(self.rooms)
            self.current_enemy = None
            self.state = "explore"
            return True
        except (OSError, ValueError, TypeError, KeyError):
            return False

