import argparse
from game.dungeon import Dungeon, generate_long_corridor
from game.view_pygame import EOBViewPG


def main() -> None:
    parser = argparse.ArgumentParser(description="CRPG Viewer")
    parser.add_argument("--test-corridor", action="store_true", help="Render a long straight corridor for visual testing")
    parser.add_argument("--corridor-length", type=int, default=101, help="Length of the test corridor (odd, >=7)")
    parser.add_argument("--corridor-height", type=int, default=9, help="Height of the test corridor (odd, >=5)")
    args = parser.parse_args()

    if args.test_corridor:
        grid = generate_long_corridor(length=args.corridor_length, height=args.corridor_height)
        dungeon = Dungeon(grid=grid, procedural=False)
    else:
        dungeon = Dungeon()
    view = EOBViewPG(dungeon)
    view.run()


if __name__ == "__main__":
    main()
