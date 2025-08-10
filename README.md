# python_crpg

Minimal terminal CRPG starter written in Python. It provides a small but complete loop: a main menu, exploration across a handful of locations, random encounters, simple turn-based combat, and basic save/load.

## Run

- Ensure Python 3.8+ is available: `python3 --version`
- Start the game: `python3 main.py`

## Gameplay

- Menu: start a New Game, Load Game, or Quit.
- Explore: move forward/back between locations, rest to heal, check inventory, or save.
- Encounters: random enemies appear while moving. Choose to attack, drink a potion, or run.
- Save/Load: writes `savegame.json` in the project root.

## Project Structure

- `main.py`: entry point that launches the game.
- `game/game.py`: game states (menu, explore, combat), world flow, save/load.
- `game/entities.py`: `Player` and `Monster` dataclasses and shared behavior.

## Next Ideas

- Add more room types, items, and loot drops.
- Expand stats (defense, accuracy, skills) and status effects.
- Add quests, shops, and a simple story arc.
- Extract UI/IO to support different frontends later.
