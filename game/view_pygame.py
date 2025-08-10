from __future__ import annotations

import sys
from typing import Tuple

import pygame

from .dungeon import Dungeon


Color = Tuple[int, int, int]


class EOBViewPG:
    def __init__(self, dungeon: Dungeon, width: int = 800, height: int = 600) -> None:
        self.dungeon = dungeon
        self.width = width
        self.height = height

        pygame.init()
        pygame.display.set_caption("CRPG - Dungeon View (Pygame)")
        self.screen = pygame.display.set_mode((self.width, self.height))
        self.clock = pygame.time.Clock()
        self.font = pygame.font.Font(None, 22)

        # Layer margins similar to Tk view
        self.margins_x = [40, 140, 220, 280]
        self.margins_y = [40, 110, 160, 200]

        # Palette
        self.color_bg = (10, 10, 12)
        self.color_floor = (20, 20, 24)
        self.color_ceiling = (16, 16, 18)
        self.color_wall = [
            (70, 70, 80),
            (90, 90, 100),
            (110, 110, 120),
            (130, 130, 140),
        ]
        self.color_outline = (30, 30, 35)
        self.color_text = (220, 220, 230)

    # ----------------- Mainloop -----------------
    def run(self) -> None:
        running = True
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key in (pygame.K_LEFT, pygame.K_a):
                        self.dungeon.turn_left()
                    elif event.key in (pygame.K_RIGHT, pygame.K_d):
                        self.dungeon.turn_right()
                    elif event.key in (pygame.K_UP, pygame.K_w):
                        self.dungeon.step_forward()
                    elif event.key in (pygame.K_DOWN, pygame.K_s):
                        self.dungeon.step_back()
                    elif event.key in (pygame.K_q,):
                        running = False

            self._draw()
            pygame.display.flip()
            self.clock.tick(60)

        pygame.quit()
        sys.exit(0)

    # ----------------- Rendering -----------------
    def _draw(self) -> None:
        W, H = self.width, self.height
        s = self.screen
        s.fill(self.color_bg)

        # Ceiling and floor
        pygame.draw.rect(s, self.color_ceiling, pygame.Rect(0, 0, W, H // 2))
        pygame.draw.rect(s, self.color_floor, pygame.Rect(0, H // 2, W, H // 2))

        # Draw far to near layers
        for d in reversed(range(4)):
            fx1, fy1, fx2, fy2 = self._front_rect(d)
            wx, wy = self.dungeon.transform_local(d + 1, 0)
            if self.dungeon.is_wall(wx, wy):
                self._rect_with_outline((fx1, fy1, fx2 - fx1, fy2 - fy1), self._wall_color(d))
                continue

            if d < 3:
                # Left side wall
                lx, ly = self.dungeon.transform_local(d + 1, -1)
                if self.dungeon.is_wall(lx, ly):
                    self._side_wall(d, left=True)
                # Right side wall
                rx, ry = self.dungeon.transform_local(d + 1, 1)
                if self.dungeon.is_wall(rx, ry):
                    self._side_wall(d, left=False)

        # HUD
        p = self.dungeon.player
        facing = ["N", "E", "S", "W"][p.facing]
        text = f"Pos: ({p.x},{p.y})  Facing: {facing}  [Arrows/WASD to move, Q to quit]"
        surf = self.font.render(text, True, self.color_text)
        s.blit(surf, (W // 2 - surf.get_width() // 2, H - 26))

    def _wall_color(self, d: int) -> Color:
        idx = max(0, min(3, d))
        return self.color_wall[idx]

    def _front_rect(self, d: int) -> tuple[int, int, int, int]:
        W, H = self.width, self.height
        mx, my = self.margins_x[d], self.margins_y[d]
        return (mx, my, W - mx, H - my)

    def _rect_with_outline(self, rect: tuple[int, int, int, int], fill: Color) -> None:
        pygame.draw.rect(self.screen, fill, rect)
        pygame.draw.rect(self.screen, self.color_outline, rect, width=2)

    def _side_wall(self, d: int, *, left: bool) -> None:
        W, H = self.width, self.height
        mx0, my0 = self.margins_x[d], self.margins_y[d]
        mx1, my1 = self.margins_x[d + 1], self.margins_y[d + 1]
        if left:
            poly = [
                (mx0, my0),
                (mx0, H - my0),
                (mx1, H - my1),
                (mx1, my1),
            ]
        else:
            poly = [
                (W - mx0, my0),
                (W - mx0, H - my0),
                (W - mx1, H - my1),
                (W - mx1, my1),
            ]
        pygame.draw.polygon(self.screen, self._wall_color(d), poly)
        pygame.draw.polygon(self.screen, self.color_outline, poly, width=2)

