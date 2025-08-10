from __future__ import annotations

import sys
from typing import Tuple

import pygame
import math
import random

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
        # Bring near layer to screen edges to avoid visible border
        self.margins_x = [0, 140, 220, 280]
        self.margins_y = [0, 110, 160, 200]

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

        # Map palette
        self.color_map_bg = (8, 8, 10)
        self.color_map_grid = (30, 30, 36)
        self.color_map_wall = (70, 70, 80)
        self.color_map_floor_unseen = (16, 16, 18)
        self.color_map_floor_seen = (140, 140, 155)
        self.color_map_player = (240, 220, 60)
        self.color_map_player_fov = (240, 220, 60)

        # Menu state
        self.menu_open = False
        self.menu_items = ["Resume", "Save", "Load", "Quit"]
        self.menu_index = 0
        self.save_path = os.path.join(os.getcwd(), "savegame.json")
        self._toast_text: str | None = None
        self._toast_until: float = 0.0

        # Map state
        self.map_open = False

        # --- Procedural textures (no external deps) ---
        self._tile_size = 64
        self._rng = random.Random(1337)
        self.tile_floor = self._gen_floor_tile(self._tile_size)
        self.tile_ceiling = self._gen_ceiling_tile(self._tile_size)
        base_wall = self._gen_brick_tile(self._tile_size)
        # Pre-tint 4 depth variants to mirror existing palette steps
        depth_factors = [0.70, 0.80, 0.92, 1.0]
        self.wall_tiles = [self._tint_surface(base_wall, f) for f in depth_factors]

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
                        if event.key == pygame.K_m:
                            self.map_open = not self.map_open
                        elif event.key in (pygame.K_LEFT, pygame.K_a):
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

        if self.map_open:
            self._draw_map()
        else:
            # Ceiling and floor with subtle torch flicker brightness
            flicker = self._flicker()
            self._blit_tiled(self.tile_ceiling, pygame.Rect(0, 0, W, H // 2), brightness=flicker)
            self._blit_tiled(self.tile_floor, pygame.Rect(0, H // 2, W, H // 2), brightness=flicker)

            # Draw far to near layers
            for d in reversed(range(4)):
                fx1, fy1, fx2, fy2 = self._front_rect(d)
                wx, wy = self.dungeon.transform_local(d + 1, 0)
                front_is_wall = self.dungeon.is_wall(wx, wy)

                if d < 3:
                    # Side walls for this depth, even if front is a wall
                    lx, ly = self.dungeon.transform_local(d + 1, -1)
                    if self.dungeon.is_wall(lx, ly):
                        self._side_wall(d, left=True)
                    rx, ry = self.dungeon.transform_local(d + 1, 1)
                    if self.dungeon.is_wall(rx, ry):
                        self._side_wall(d, left=False)

                if front_is_wall:
                    # Draw front-facing wall after side walls for correct overlap
                    rect = pygame.Rect(fx1, fy1, fx2 - fx1, fy2 - fy1)
                    self._blit_tiled(self.wall_tiles[d], rect)
                    pygame.draw.rect(s, self.color_outline, rect, width=2)
                    continue

        # HUD
        p = self.dungeon.player
        facing = ["N", "E", "S", "W"][p.facing]
        extra = " • M: Map" if not self.map_open else " • M: Close Map"
        text = f"Pos: ({p.x},{p.y})  Facing: {facing}  [Arrows/WASD to move, ESC menu{extra}]"
        surf = self.font.render(text, True, self.color_text)
        s.blit(surf, (W // 2 - surf.get_width() // 2, H - 26))

        # Toast messages (e.g., save/load feedback)
        if self._toast_text and time.time() < self._toast_until:
            tsurf = self.font.render(self._toast_text, True, self.color_text)
            s.blit(tsurf, (W // 2 - tsurf.get_width() // 2, H - 50))

        # Menu overlay
        if self.menu_open:
            self._draw_menu()

    def _draw_map(self) -> None:
        W, H = self.width, self.height
        s = self.screen
        s.fill(self.color_map_bg)

        grid = self.dungeon.grid
        visited = self.dungeon.visited
        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        if rows == 0 or cols == 0:
            return

        # Compute tile size with some margin
        margin = 40
        available_w = W - margin * 2
        available_h = H - margin * 2
        tile_w = max(2, min(32, available_w // cols))
        tile_h = max(2, min(32, available_h // rows))
        tile = min(tile_w, tile_h)
        map_w = tile * cols
        map_h = tile * rows
        offset_x = (W - map_w) // 2
        offset_y = (H - map_h) // 2

        # Draw grid background and cells
        for y in range(rows):
            for x in range(cols):
                rx = offset_x + x * tile
                ry = offset_y + y * tile
                rect = pygame.Rect(rx, ry, tile, tile)
                if grid[y][x] == 1:
                    pygame.draw.rect(s, self.color_map_wall, rect)
                else:
                    color = self.color_map_floor_seen if visited[y][x] else self.color_map_floor_unseen
                    pygame.draw.rect(s, color, rect)

        # Grid lines to delineate cells
        for y in range(rows + 1):
            ypix = offset_y + y * tile
            pygame.draw.line(s, self.color_map_grid, (offset_x, ypix), (offset_x + map_w, ypix), 1)
        for x in range(cols + 1):
            xpix = offset_x + x * tile
            pygame.draw.line(s, self.color_map_grid, (xpix, offset_y), (xpix, offset_y + map_h), 1)

        # Draw player position and facing
        p = self.dungeon.player
        px = offset_x + p.x * tile + tile // 2
        py = offset_y + p.y * tile + tile // 2
        r = max(3, tile // 3)
        pygame.draw.circle(s, self.color_map_player, (px, py), r)
        # Facing indicator
        dir_vecs = [(0, -1), (1, 0), (0, 1), (-1, 0)]
        dx, dy = dir_vecs[p.facing]
        tip_x = px + int(dx * r * 1.6)
        tip_y = py + int(dy * r * 1.6)
        pygame.draw.line(s, self.color_map_player, (px, py), (tip_x, tip_y), 2)

        # Title / legend
        title = self.font_large.render("Dungeon Map", True, self.color_text)
        s.blit(title, (W // 2 - title.get_width() // 2, offset_y - 30))
        legend = self.font.render("#: wall  • dark: unseen  • light: visited  • dot+arrow: you", True, self.color_text)
        s.blit(legend, (W // 2 - legend.get_width() // 2, offset_y + map_h + 10))

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
        # Texture-map side wall by tiling and masking to polygon
        self._blit_tiled_polygon(self.wall_tiles[d], poly)
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

    # ----------------- Texture helpers -----------------
    def _randf(self, a: float, b: float) -> float:
        return self._rng.uniform(a, b)

    def _gen_floor_tile(self, sz: int) -> pygame.Surface:
        # Checker base with noise speckle and soft vignette
        surf = pygame.Surface((sz, sz)).convert()
        c1 = (45, 45, 52)
        c2 = (50, 50, 58)
        cell = sz // 8 or 8
        for y in range(0, sz, cell):
            for x in range(0, sz, cell):
                r = ((x // cell) + (y // cell)) % 2
                color = c1 if r == 0 else c2
                pygame.draw.rect(surf, color, (x, y, cell, cell))
        # Speckle
        arr = pygame.PixelArray(surf)
        for _ in range(sz * 16):
            x = self._rng.randrange(0, sz)
            y = self._rng.randrange(0, sz)
            shade = self._rng.randrange(-6, 7)
            col = surf.unmap_rgb(arr[x, y])
            r, g, b = col.r, col.g, col.b
            nr, ng, nb = max(0, min(255, r + shade)), max(0, min(255, g + shade)), max(0, min(255, b + shade))
            arr[x, y] = surf.map_rgb((nr, ng, nb))
        del arr
        return surf.convert()

    def _gen_ceiling_tile(self, sz: int) -> pygame.Surface:
        # Soft vertical gradient with subtle noise
        surf = pygame.Surface((sz, sz)).convert()
        top = self.color_ceiling
        bot = (max(0, top[0] - 6), max(0, top[1] - 6), max(0, top[2] - 6))
        for y in range(sz):
            t = y / (sz - 1)
            r = int(top[0] * (1 - t) + bot[0] * t)
            g = int(top[1] * (1 - t) + bot[1] * t)
            b = int(top[2] * (1 - t) + bot[2] * t)
            pygame.draw.line(surf, (r, g, b), (0, y), (sz, y))
        # Speckle
        arr = pygame.PixelArray(surf)
        for _ in range(sz * 8):
            x = self._rng.randrange(0, sz)
            y = self._rng.randrange(0, sz)
            shade = self._rng.randrange(-4, 5)
            col = surf.unmap_rgb(arr[x, y])
            r, g, b = col.r, col.g, col.b
            arr[x, y] = surf.map_rgb((max(0, min(255, r + shade)), max(0, min(255, g + shade)), max(0, min(255, b + shade))))
        del arr
        return surf.convert()

    def _gen_brick_tile(self, sz: int) -> pygame.Surface:
        surf = pygame.Surface((sz, sz)).convert()
        base = (95, 96, 108)
        mortar = (58, 58, 66)
        surf.fill(base)
        # Brick layout (rows with offset)
        rows = 6
        brick_h = sz // rows
        mortar_t = max(1, brick_h // 10)
        for row in range(rows):
            y0 = row * brick_h
            # horizontal mortar
            pygame.draw.rect(surf, mortar, (0, y0, sz, mortar_t))
            # bricks per row
            offset = (row % 2) * (sz // 6)
            brick_w = sz // 3
            for col in range(-1, 4):
                x0 = col * brick_w + offset
                # vertical mortar
                pygame.draw.rect(surf, mortar, (x0, y0, mortar_t, brick_h))
        # Subtle per-pixel variation
        arr = pygame.PixelArray(surf)
        for y in range(sz):
            for x in range(sz):
                if self._rng.random() < 0.06:
                    shade = self._rng.randrange(-10, 11)
                    col = surf.unmap_rgb(arr[x, y])
                    r, g, b = col.r, col.g, col.b
                    arr[x, y] = surf.map_rgb((max(0, min(255, r + shade)), max(0, min(255, g + shade)), max(0, min(255, b + shade))))
        del arr
        return surf.convert()

    def _tint_surface(self, src: pygame.Surface, factor: float) -> pygame.Surface:
        # Multiply brightness by factor using a copy
        surf = src.copy().convert()
        # Create a solid color surface and blend multiply-ish using special_flags
        tint = pygame.Surface(surf.get_size()).convert()
        val = max(0, min(255, int(255 * factor)))
        tint.fill((val, val, val))
        surf.blit(tint, (0, 0), special_flags=pygame.BLEND_MULT)
        return surf

    def _blit_tiled(self, tile: pygame.Surface, rect: pygame.Rect, *, brightness: float = 1.0) -> None:
        # Optionally apply brightness by blitting a tinted copy once per call
        if brightness != 1.0:
            tile = self._tint_surface(tile, brightness)
        ts = tile.get_size()
        x0, y0, w, h = rect
        prev_clip = self.screen.get_clip()
        self.screen.set_clip(rect)
        try:
            for y in range(y0, y0 + h, ts[1]):
                for x in range(x0, x0 + w, ts[0]):
                    self.screen.blit(tile, (x, y))
        finally:
            self.screen.set_clip(prev_clip)

    def _flicker(self) -> float:
        # Smooth flicker from combined sines
        t = pygame.time.get_ticks() / 1000.0
        v = 0.5 * (math.sin(t * 2.1) + math.sin(t * 2.7 + 1.3))
        return 0.96 + 0.06 * v  # ~0.90..1.02

    def _poly_hatch(self, poly: list[tuple[int, int]], intensity: int = 24) -> None:
        # Draw faint vertical stripes clipped to polygon
        if not poly:
            return
        min_x = min(p[0] for p in poly)
        max_x = max(p[0] for p in poly)
        min_y = min(p[1] for p in poly)
        max_y = max(p[1] for p in poly)
        w = max(1, max_x - min_x)
        h = max(1, max_y - min_y)
        step = 8
        stripes = pygame.Surface((w, h), pygame.SRCALPHA)
        line_color = (40, 40, 46, max(1, min(255, intensity)))
        for x in range(step // 2, w, step):
            pygame.draw.line(stripes, line_color, (x, 0), (x, h), 1)
        mask = pygame.Surface((w, h), pygame.SRCALPHA)
        shifted = [(x - min_x, y - min_y) for (x, y) in poly]
        pygame.draw.polygon(mask, (255, 255, 255, 255), shifted)
        stripes.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        self.screen.blit(stripes, (min_x, min_y))

    def _blit_tiled_polygon(self, tile: pygame.Surface, poly: list[tuple[int, int]]) -> None:
        if not poly:
            return
        min_x = min(p[0] for p in poly)
        max_x = max(p[0] for p in poly)
        min_y = min(p[1] for p in poly)
        max_y = max(p[1] for p in poly)
        w = max(1, max_x - min_x)
        h = max(1, max_y - min_y)

        # Tile into an offscreen surface
        tiled = pygame.Surface((w, h), pygame.SRCALPHA)
        ts = tile.get_size()
        for y in range(0, h, ts[1]):
            for x in range(0, w, ts[0]):
                tiled.blit(tile, (x, y))

        # Build a mask for the polygon and multiply to clip
        mask = pygame.Surface((w, h), pygame.SRCALPHA)
        shifted = [(x - min_x, y - min_y) for (x, y) in poly]
        pygame.draw.polygon(mask, (255, 255, 255, 255), shifted)
        tiled.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)

        # Blit to screen
        self.screen.blit(tiled, (min_x, min_y))
