from game.dungeon import Dungeon
from game.view_pygame import EOBViewPG


def main() -> None:
    dungeon = Dungeon()
    view = EOBViewPG(dungeon)
    view.run()


if __name__ == "__main__":
    main()
