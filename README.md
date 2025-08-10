# python_crpg

A minimal grid-based, first-person dungeon crawler in the style of Eye of the Beholder, rendered with Pygame. Movement is step-based on a 2D grid while the view renders a faux-3D corridor using layered wall slices.

## Setup (pyenv + venv)

This project uses pyenv to pin a Python version and a local virtualenv via the Makefile.

1) Install pyenv
- macOS: `brew install pyenv`
- Linux: follow https://github.com/pyenv/pyenv#installation
- Windows: use WSL + pyenv, or install Python 3.12 from python.org and skip pyenv.

2) Install and select Python
- `pyenv install 3.12.5`
- `pyenv local 3.12.5` (repo includes `.python-version`)

3) Create venv and install deps
- `make install`

## Run

- `make run`

## Gameplay

- Movement: arrows or WASD to turn/move; `Q` quits.
- View: layered wall slices draw front and side walls for 4 depths.
- Map: press `M` to toggle a top-down map. It shows walls (gray), visited floors (light), unseen (dark), you (yellow), monsters (red), gold (yellow squares), and weapons (blue squares).
- Entities: monsters roam the dungeon; stepping toward a monster triggers simple combat. Pick up gold by stepping onto it. Weapons improve your attack when equipped automatically if better than current.
 - Monsters now render in the 3D corridor as simple billboard sprites with distance fog.

## Project Structure

- `main.py`: entry point launching the Pygame view.
- `game/dungeon.py`: map grid, player state, and movement.
- `game/view_pygame.py`: Pygame renderer for an Eye-of-the-Beholder-style view.

## Makefile

- `make venv`: create a virtual environment in `.venv`.
- `make install`: install `requirements.txt` into the venv.
- `make run`: run the game within the venv.
- `make freeze`: export current venv packages to `requirements.txt`.
- `make clean`: remove venv and Python cache files.
- `make doctor`: verify Tkinter is available in your Python/venv.

If Tkinter is missing on your Python, the game will use Pygame instead. If you see import errors for Pygame, run `make install` (network required to download wheels).

## Next Ideas

- Add sprites/textures for walls, floor, UI widgets.
- Add automap and minimap overlay.
- Add entities (monsters, items) and interactions in 3D view.
- Add step-animations and sound.
