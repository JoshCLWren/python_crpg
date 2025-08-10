from __future__ import annotations

import sys
from typing import Tuple

import pygame

from .dungeon import Dungeon
import os
import time


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
        self.font_large = pygame.font.Font(None, 28)

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
        self.color_menu_bg = (0, 0, 0, 170)  # semi-transparent
        self.color_menu_box = (25, 25, 30)
        self.color_menu_highlight = (80, 120, 220)

        # Menu state
        self.menu_open = False
        self.menu_items = ["Resume", "Save", "Load", "Quit"]
        self.menu_index = 0
        self.save_path = os.path.join(os.getcwd(), "savegame.json")
        self._toast_text: str | None = None
        self._toast_until: float = 0.0

    # ----------------- Mainloop -----------------
    def run(self) -> None:
        running = True
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        self.menu_open = not self.menu_open
                    elif self.menu_open:
                        if event.key in (pygame.K_UP, pygame.K_w):
                            self.menu_index = (self.menu_index - 1) % len(self.menu_items)
                        elif event.key in (pygame.K_DOWN, pygame.K_s):
                            self.menu_index = (self.menu_index + 1) % len(self.menu_items)
                        elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                            choice = self.menu_items[self.menu_index]
                            if choice == "Resume":
                                self.menu_open = False
                            elif choice == "Save":
                                self._handle_save()
                            elif choice == "Load":
                                self._handle_load()
                            elif choice == "Quit":
                                running = False
                    else:
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
        text = f"Pos: ({p.x},{p.y})  Facing: {facing}  [Arrows/WASD to move, ESC menu]"
        surf = self.font.render(text, True, self.color_text)
        s.blit(surf, (W // 2 - surf.get_width() // 2, H - 26))

        # Toast messages (e.g., save/load feedback)
        if self._toast_text and time.time() < self._toast_until:
            tsurf = self.font.render(self._toast_text, True, self.color_text)
            s.blit(tsurf, (W // 2 - tsurf.get_width() // 2, H - 50))

        # Menu overlay
        if self.menu_open:
            self._draw_menu()

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

    # ----------------- UI Helpers -----------------
    def _draw_menu(self) -> None:
        W, H = self.width, self.height
        # Dim background
        overlay = pygame.Surface((W, H), pygame.SRCALPHA)
        overlay.fill(self.color_menu_bg)
        self.screen.blit(overlay, (0, 0))

        # Menu box
        box_w, box_h = 360, 240
        box_x, box_y = (W - box_w) // 2, (H - box_h) // 2
        pygame.draw.rect(self.screen, self.color_menu_box, (box_x, box_y, box_w, box_h), border_radius=8)
        pygame.draw.rect(self.screen, self.color_outline, (box_x, box_y, box_w, box_h), width=2, border_radius=8)

        # Title
        title = self.font_large.render("Menu", True, self.color_text)
        self.screen.blit(title, (W // 2 - title.get_width() // 2, box_y + 16))

        # Items
        start_y = box_y + 60
        line_h = 36
        for idx, label in enumerate(self.menu_items):
            if idx == self.menu_index:
                # highlight background
                hx, hy = box_x + 20, start_y + idx * line_h - 6
                pygame.draw.rect(self.screen, self.color_menu_highlight, (hx, hy, box_w - 40, line_h), border_radius=6)
                color = (20, 20, 24)
            else:
                color = self.color_text
            surf = self.font_large.render(label, True, color)
            self.screen.blit(surf, (W // 2 - surf.get_width() // 2, start_y + idx * line_h))

        # Footer hint
        hint = self.font.render("↑/↓ to navigate • Enter to select • ESC to close", True, self.color_text)
        self.screen.blit(hint, (W // 2 - hint.get_width() // 2, box_y + box_h - 28))

    def _toast(self, text: str, seconds: float = 1.8) -> None:
        self._toast_text = text
        self._toast_until = time.time() + seconds

    def _handle_save(self) -> None:
        try:
            self.dungeon.save_to_file(self.save_path)
            self._toast("Game saved.")
        except Exception as e:
            self._toast(f"Save failed: {e}")

    def _handle_load(self) -> None:
        try:
            if not os.path.exists(self.save_path):
                self._toast("No save found.")
                return
            self.dungeon.load_from_file(self.save_path)
            self._toast("Game loaded.")
        except Exception as e:
            self._toast(f"Load failed: {e}")
