from __future__ import annotations

import sys
from typing import Tuple

import pygame
import math
import random
import json

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

        # Layer config: 16 layers using 4-anchor piecewise interpolation
        # 50/50 floor-ceiling split; anchors define near..far geometry
        self.layers = 16
        self.margins_x = [0, 160, 260, 320]
        self.margins_y = [0, 140, 210, 260]

        # Live tuning support
        self.tuning_mode = False
        self.tuning_path = os.path.join(os.getcwd(), "view_tuning.json")
        self._load_tuning()
        # Auto-layers (vary slices by visible distance)
        self.auto_layers = True
        self._render_layers: int | None = None
        self._layers_base = 6   # minimum when corridor starts opening up
        self._layers_per_tile = 2  # add slices per forward tile
        # Far cap to avoid black void at max range
        self.cap_far = True
        # Distance fog (darken last few layers)
        self.fog_enabled = True
        self.fog_layers = 8  # number of far layers affected
        self.fog_far = 0.50  # brightness at the farthest layer
        self.fog_alpha_far = 0.30  # opacity at the farthest layer (0..1)
        self.fog_overlay_alpha_far = 0.60  # additional screen-space fog over far ring
        self.fog_min_start = 6  # do not fog nearer than this layer index
        self._nearest_front: int | None = None
        # Tuning hold behavior
        self._acc_far_x_inc = 0.0
        self._acc_far_x_dec = 0.0
        self._acc_far_y_inc = 0.0
        self._acc_far_y_dec = 0.0
        self._acc_near_x_inc = 0.0
        self._acc_near_x_dec = 0.0
        self._acc_near_y_inc = 0.0
        self._acc_layer_inc = 0.0
        self._acc_layer_dec = 0.0
        # Speeds (pixels per second) and rate (steps/sec)
        self._spd_far_x = 220.0
        self._spd_far_y = 220.0
        self._spd_near_x = 120.0
        self._spd_near_y = 120.0
        self._rate_layers = 8.0

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
        # Procedural monster sprites
        self.monster_sprites = self._gen_monster_sprites(64)

        # --- Motion cues: texture scroll on floor/ceiling ---
        self._floor_scroll_y = 0.0
        self._ceiling_scroll_y = 0.0
        self._pending_scroll_y = 0.0
        self._scroll_speed = 420.0  # pixels per second
        # Track previous player state for step detection
        self._prev_px = dungeon.player.x
        self._prev_py = dungeon.player.y
        self._prev_facing = dungeon.player.facing

        # --- Key-hold movement repeat ---
        self._hold_repeat_delay_move = 0.22
        self._hold_repeat_rate_move = 0.11
        self._hold_repeat_delay_turn = 0.22
        self._hold_repeat_rate_turn = 0.12
        self._hold_state = {
            "forward": {"was_down": False, "acc": 0.0},
            "back": {"was_down": False, "acc": 0.0},
            "turn_left": {"was_down": False, "acc": 0.0},
            "turn_right": {"was_down": False, "acc": 0.0},
        }

        # --- Vanishing-point perspective (always on) ---
        self.use_vanishing = True
        # Controls how quickly geometry converges; lower = faster convergence
        # Smaller = faster convergence (larger spacing between near wall slices)
        self.vp_depth_x = 3.0
        self.vp_depth_y = 6.0

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
                        elif event.key == pygame.K_l:
                            self.auto_layers = not self.auto_layers
                        elif event.key == pygame.K_t:
                            self.tuning_mode = not self.tuning_mode
                            if not self.tuning_mode:
                                self._save_tuning()
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
                        # --- Tuning keys ---
                        elif self.tuning_mode:
                            if event.key == pygame.K_LEFTBRACKET:  # [
                                self.margins_x[-1] -= 5
                                self._clamp_anchors()
                            elif event.key == pygame.K_RIGHTBRACKET:  # ]
                                self.margins_x[-1] += 5
                                self._clamp_anchors()
                            elif event.key == pygame.K_SEMICOLON:  # ;
                                self.margins_y[-1] += 5  # increase top/bottom margin -> shorter far wall
                                self._clamp_anchors()
                            elif event.key == pygame.K_QUOTE:  # '
                                self.margins_y[-1] -= 5
                                self._clamp_anchors()
                            elif event.key == pygame.K_COMMA:  # , adjust near inset X
                                self.margins_x[0] = max(0, self.margins_x[0] - 2)
                                self._clamp_anchors()
                            elif event.key == pygame.K_PERIOD:  # .
                                self.margins_x[0] = min(self.width // 4, self.margins_x[0] + 2)
                                self._clamp_anchors()
                            elif event.key == pygame.K_SLASH:  # /
                                self.margins_y[0] = min(self.height // 4, self.margins_y[0] + 2)
                                self._clamp_anchors()
                            elif event.key == pygame.K_RSHIFT or event.key == pygame.K_LSHIFT:
                                pass
                            elif event.key == pygame.K_MINUS:  # - layers down
                                self.layers = max(4, self.layers - 1)
                            elif event.key == pygame.K_EQUALS:  # = layers up
                                self.layers = min(32, self.layers + 1)
                            elif event.key == pygame.K_r:
                                # Reset to defaults
                                self.layers = 16
                                self.margins_x = [0, 160, 260, 320]
                                self.margins_y = [0, 140, 210, 260]
                            elif event.key == pygame.K_s:
                                self._save_tuning()

            # Apply held-key repeats using the last frame's dt
            dt = self.clock.get_time() / 1000.0
            self._process_hold(dt)

            # Pull any game messages from dungeon (pickups/combat)
            for msg in self.dungeon.drain_messages():
                self._toast(msg)

            self._draw()
            pygame.display.flip()
            self.clock.tick(60)
            # Continuous tuning adjustments while keys are held
            if self.tuning_mode and not self.menu_open:
                dt = self.clock.get_time() / 1000.0
                self._update_tuning_held(dt)

        pygame.quit()
        sys.exit(0)

    # ----------------- Rendering -----------------
    def _draw(self) -> None:
        W, H = self.width, self.height
        s = self.screen
        s.fill(self.color_bg)

        # Detect step to trigger texture scroll
        p = self.dungeon.player
        if (p.x, p.y) != (self._prev_px, self._prev_py):
            dx = p.x - self._prev_px
            dy = p.y - self._prev_py
            # Facing vector from previous frame
            dir_vecs = [(0, -1), (1, 0), (0, 1), (-1, 0)]
            fdx, fdy = dir_vecs[self._prev_facing]
            if (dx, dy) == (fdx, fdy):
                # Forward step: scroll floor towards camera
                self._pending_scroll_y += self._tile_size
            elif (dx, dy) == (-fdx, -fdy):
                # Backwards step: scroll away
                self._pending_scroll_y -= self._tile_size
            # Update stored state
            self._prev_px, self._prev_py, self._prev_facing = p.x, p.y, p.facing

        # Apply scroll animation incrementally based on frame time
        dt = self.clock.get_time() / 1000.0
        if self._pending_scroll_y != 0.0:
            step = self._scroll_speed * dt
            if abs(step) > abs(self._pending_scroll_y):
                step = abs(self._pending_scroll_y)
            step *= 1 if self._pending_scroll_y > 0 else -1
            self._floor_scroll_y += step
            self._ceiling_scroll_y += step * 0.5  # subtler on ceiling
            self._pending_scroll_y -= step
            # Keep offsets bounded [0, tile)
            ts = self._tile_size
            self._floor_scroll_y %= ts
            self._ceiling_scroll_y %= ts

        if self.map_open:
            self._draw_map()
        else:
            # Ceiling and floor with subtle torch flicker brightness
            flicker = self._flicker()
            self._blit_tiled(self.tile_ceiling, pygame.Rect(0, 0, W, H // 2), brightness=flicker, alpha=255, offset=(0, int(self._ceiling_scroll_y)))
            self._blit_tiled(self.tile_floor, pygame.Rect(0, H // 2, W, H // 2), brightness=flicker, alpha=255, offset=(0, int(self._floor_scroll_y)))

            # Determine dynamic layer count based on visible distance (per world tile)
            # Also precompute nearest blocking wall straight ahead
            nearest_front: int | None = None
            max_probe = 256
            for k in range(max_probe):
                wxk, wyk = self.dungeon.transform_local(k + 1, 0)
                if self.dungeon.is_wall(wxk, wyk):
                    nearest_front = k
                    break

            # Layers now map to world tiles: render up to the hit tile, else up to geometry limit
            if nearest_front is not None:
                dyn_layers = nearest_front + 1  # include the front face layer
            else:
                dyn_layers = self._geom_depth_limit()
            self._render_layers = dyn_layers
            self._nearest_front = nearest_front

            # Draw far to near layers
            for d in reversed(range(dyn_layers)):
                fx1, fy1, fx2, fy2 = self._front_rect(d)
                wx, wy = self.dungeon.transform_local(d + 1, 0)
                front_is_wall = self.dungeon.is_wall(wx, wy)

                # Draw side walls up to the layer before the front in vanishing mode;
                # in anchor mode, cap to available anchors to avoid degenerate polys.
                if getattr(self, "use_vanishing", False):
                    side_ok = d < dyn_layers - 1
                else:
                    side_ok = d < min(dyn_layers - 1, len(self.margins_x) - 1, len(self.margins_y) - 1)
                if side_ok:
                    # Side walls for this depth, even if front is a wall
                    lx, ly = self.dungeon.transform_local(d + 1, -1)
                    if self.dungeon.is_wall(lx, ly):
                        self._side_wall(d, left=True)
                    rx, ry = self.dungeon.transform_local(d + 1, 1)
                    if self.dungeon.is_wall(rx, ry):
                        self._side_wall(d, left=False)

                if front_is_wall and (nearest_front is None or d == nearest_front):
                    # Draw front-facing wall after side walls for correct overlap
                    rect = pygame.Rect(fx1, fy1, fx2 - fx1, fy2 - fy1)
                    base_tile = self.wall_tiles[min(d, len(self.wall_tiles) - 1)]
                    tile = base_tile
                    alpha = 255
                    if self.fog_enabled:
                        # Never fog the nearest blocking front wall
                        if self._nearest_front is not None and d == self._nearest_front:
                            fog_b, fog_a = 1.0, 1.0
                        else:
                            fog_b, fog_a = self._fog_params(d, dyn_layers)
                        tile = self._tint_surface(base_tile, fog_b)
                        alpha = int(255 * fog_a)
                    self._blit_tiled(tile, rect, alpha=alpha)
                    # Skip outlines in fog zone to avoid visual density
                    if not self._in_fog_zone(d, dyn_layers):
                        pygame.draw.rect(s, self.color_outline, rect, width=2)
                    continue
            # If no wall in sight and cap is enabled, draw a dim far cap at the last layer
            if nearest_front is None and self.cap_far:
                d = dyn_layers - 1
                fx1, fy1, fx2, fy2 = self._front_rect(d)
                rect = pygame.Rect(fx1, fy1, fx2 - fx1, fy2 - fy1)
                tile = self.wall_tiles[-1]
                fog_b = self.fog_far if self.fog_enabled else 0.6
                fog_a = self.fog_alpha_far if self.fog_enabled else 1.0
                capped = self._tint_surface(tile, fog_b)
                self._blit_tiled(capped, rect, alpha=int(255 * fog_a))
                if fog_a > 0.9:
                    pygame.draw.rect(s, self.color_outline, rect, width=2)
                # Will overlay fog rings after all geometry
            # Draw monsters within visible depth before fog overlays
            self._draw_monsters(dyn_layers)

            # Overlay fog rings after all geometry so fade is visible
            if self.fog_enabled:
                self._draw_fog_overlays(dyn_layers)
            # Clear per-frame layers after draw
            self._render_layers = None
            self._nearest_front = None

        # HUD
        facing = ["N", "E", "S", "W"][p.facing]
        extra = " • M: Map" if not self.map_open else " • M: Close Map"
        weapon = p.weapon or "Fists"
        text = (
            f"Pos: ({p.x},{p.y})  Facing: {facing}  HP: {p.hp}  Gold: {p.gold}  "
            f"Weapon: {weapon} (+{p.weapon_atk})  [Arrows/WASD to move, ESC menu{extra}]"
        )
        surf = self.font.render(text, True, self.color_text)
        s.blit(surf, (W // 2 - surf.get_width() // 2, H - 26))

        # Toast messages (e.g., save/load feedback)
        if self._toast_text and time.time() < self._toast_until:
            tsurf = self.font.render(self._toast_text, True, self.color_text)
            s.blit(tsurf, (W // 2 - tsurf.get_width() // 2, H - 50))

        # Menu overlay
        if self.menu_open:
            self._draw_menu()
        # Tuning overlay
        if self.tuning_mode and not self.menu_open:
            self._draw_tuning_overlay()

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

        # Draw items (gold/weapons)
        for it in getattr(self.dungeon, "items", []):
            rx = offset_x + it.x * tile
            ry = offset_y + it.y * tile
            rect = pygame.Rect(rx + tile // 4, ry + tile // 4, max(2, tile // 2), max(2, tile // 2))
            if getattr(it, "kind", "") == "gold":
                color = (220, 200, 60)  # gold
            else:
                color = (80, 180, 240)  # weapon
            pygame.draw.rect(s, color, rect)

        # Draw monsters
        for m in getattr(self.dungeon, "monsters", []):
            rx = offset_x + m.x * tile + tile // 2
            ry = offset_y + m.y * tile + tile // 2
            rr = max(3, tile // 3)
            pygame.draw.circle(s, (200, 60, 60), (rx, ry), rr)  # red

        # Draw player position and facing (on top)
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
        mx = self._mx(d)
        my = self._my(d)
        return (mx, my, W - mx, H - my)

    def _rect_with_outline(self, rect: tuple[int, int, int, int], fill: Color) -> None:
        pygame.draw.rect(self.screen, fill, rect)
        pygame.draw.rect(self.screen, self.color_outline, rect, width=2)

    def _side_wall(self, d: int, *, left: bool) -> None:
        W, H = self.width, self.height
        mx0, my0 = self._mx(d), self._my(d)
        mx1, my1 = self._mx(d + 1), self._my(d + 1)
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
        base_tile = self.wall_tiles[min(d, len(self.wall_tiles) - 1)]
        tile = base_tile
        layers = self._render_layers if self._render_layers is not None else self.layers
        alpha = 255
        if self.fog_enabled:
            # Do not fog side faces at or before the nearest blocking front
            if self._nearest_front is not None and d <= self._nearest_front:
                fog_b, fog_a = 1.0, 1.0
            else:
                fog_b, fog_a = self._fog_params(d, layers)
            tile = self._tint_surface(base_tile, fog_b)
            alpha = int(255 * fog_a)
        self._blit_tiled_polygon(tile, poly, alpha=alpha)
        if not self._in_fog_zone(d, layers):
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

    def _blit_tiled(self, tile: pygame.Surface, rect: pygame.Rect, *, brightness: float = 1.0, alpha: int = 255, offset: tuple[int, int] | None = None) -> None:
        # Optionally apply brightness by blitting a tinted copy once per call
        if brightness != 1.0:
            tile = self._tint_surface(tile, brightness)
        ts = tile.get_size()
        x0, y0, w, h = rect
        ox, oy = (0, 0) if offset is None else (offset[0] % ts[0], offset[1] % ts[1])
        if alpha >= 255:
            prev_clip = self.screen.get_clip()
            self.screen.set_clip(rect)
            try:
                start_y = y0 - oy
                start_x = x0 - ox
                for y in range(start_y, y0 + h, ts[1]):
                    for x in range(start_x, x0 + w, ts[0]):
                        self.screen.blit(tile, (x, y))
            finally:
                self.screen.set_clip(prev_clip)
        else:
            patch = pygame.Surface((w, h), pygame.SRCALPHA)
            start_y = -oy
            start_x = -ox
            for y in range(start_y, h, ts[1]):
                for x in range(start_x, w, ts[0]):
                    patch.blit(tile, (x, y))
            patch.set_alpha(max(0, min(255, alpha)))
            self.screen.blit(patch, (x0, y0))

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

    def _blit_tiled_polygon(self, tile: pygame.Surface, poly: list[tuple[int, int]], alpha: int = 255) -> None:
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
        if alpha < 255:
            tiled.set_alpha(max(0, min(255, alpha)))

        # Blit to screen
        self.screen.blit(tiled, (min_x, min_y))

    def _scale_surface(self, src: pygame.Surface, w: int, h: int) -> pygame.Surface:
        w = max(1, w)
        h = max(1, h)
        if w == src.get_width() and h == src.get_height():
            return src
        try:
            return pygame.transform.smoothscale(src, (w, h))
        except Exception:
            return pygame.transform.scale(src, (w, h))

    # ----------------- Monsters (3D) -----------------
    def _draw_monsters(self, layers: int) -> None:
        if not getattr(self.dungeon, "monsters", None):
            return
        nearest = self._nearest_front if self._nearest_front is not None else None
        for d in reversed(range(layers)):
            # If a front wall is at or nearer than d, treat as occluder
            if nearest is not None and d >= nearest:
                continue
            fx1, fy1, fx2, fy2 = self._front_rect(d)
            band_w = max(1, fx2 - fx1)
            band_h = max(1, fy2 - fy1)
            # Target sprite size based on depth window
            spr_h = int(band_h * 0.55)
            spr_w = int(min(band_w * 0.30, spr_h * 0.9))
            cx = (fx1 + fx2) // 2
            left_cx = fx1 + band_w // 4
            right_cx = fx2 - band_w // 4
            for r_off, cxpos in ((-1, left_cx), (0, cx), (1, right_cx)):
                wx, wy = self.dungeon.transform_local(d + 1, r_off)
                if self.dungeon.is_wall(wx, wy):
                    continue
                # Find a monster at tile
                mon = None
                for m in self.dungeon.monsters:
                    if m.x == wx and m.y == wy:
                        mon = m
                        break
                if mon is None:
                    continue
                sprite = self._get_monster_sprite(mon.name)
                alpha = 255
                if self.fog_enabled:
                    fog_b, fog_a = self._fog_params(d, layers)
                    sprite = self._tint_surface(sprite, fog_b)
                    alpha = int(255 * fog_a)
                scaled = self._scale_surface(sprite, spr_w, spr_h)
                scaled.set_alpha(max(0, min(255, alpha)))
                x = int(cxpos - scaled.get_width() // 2)
                y = int((fy1 + fy2) // 2 - scaled.get_height() // 2)
                self.screen.blit(scaled, (x, y))

    def _get_monster_sprite(self, name: str) -> pygame.Surface:
        key = name.lower()
        if "rat" in key:
            return self.monster_sprites["rat"]
        if "skeleton" in key:
            return self.monster_sprites["skeleton"]
        if "bat" in key:
            return self.monster_sprites["bat"]
        return self.monster_sprites.get("goblin")

    def _gen_monster_sprites(self, sz: int) -> dict[str, pygame.Surface]:
        sprites: dict[str, pygame.Surface] = {}
        sprites["goblin"] = self._draw_face_sprite(sz, (36, 120, 52), eye=(250, 250, 255), mouth=(180, 40, 40))
        sprites["skeleton"] = self._draw_skull_sprite(sz)
        sprites["rat"] = self._draw_face_sprite(sz, (90, 90, 100), eye=(240, 80, 80), mouth=(60, 60, 70), ears=True)
        sprites["bat"] = self._draw_bat_sprite(sz)
        return sprites

    def _draw_face_sprite(self, sz: int, base: tuple[int, int, int], *, eye: tuple[int, int, int], mouth: tuple[int, int, int], ears: bool = False) -> pygame.Surface:
        s = pygame.Surface((sz, sz), pygame.SRCALPHA)
        # Head
        pygame.draw.ellipse(s, base, (int(sz*0.10), int(sz*0.18), int(sz*0.80), int(sz*0.70)))
        # Ears
        if ears:
            pygame.draw.polygon(s, base, [(int(sz*0.20), int(sz*0.20)), (int(sz*0.10), int(sz*0.05)), (int(sz*0.30), int(sz*0.15))])
            pygame.draw.polygon(s, base, [(int(sz*0.80), int(sz*0.20)), (int(sz*0.90), int(sz*0.05)), (int(sz*0.70), int(sz*0.15))])
        # Eyes
        eye_w, eye_h = int(sz*0.14), int(sz*0.16)
        pygame.draw.ellipse(s, eye, (int(sz*0.28), int(sz*0.36), eye_w, eye_h))
        pygame.draw.ellipse(s, eye, (int(sz*0.58), int(sz*0.36), eye_w, eye_h))
        # Pupils
        pygame.draw.circle(s, (10, 10, 14), (int(sz*0.28+eye_w*0.5), int(sz*0.36+eye_h*0.55)), max(1, sz//32))
        pygame.draw.circle(s, (10, 10, 14), (int(sz*0.58+eye_w*0.5), int(sz*0.36+eye_h*0.55)), max(1, sz//32))
        # Mouth
        pygame.draw.ellipse(s, mouth, (int(sz*0.36), int(sz*0.62), int(sz*0.28), int(sz*0.12)))
        # Teeth
        for i in range(3):
            x = int(sz*0.38 + i*sz*0.09)
            pygame.draw.rect(s, (240, 240, 240), (x, int(sz*0.64), max(1, sz//28), int(sz*0.06)))
        return s.convert_alpha()

    def _draw_skull_sprite(self, sz: int) -> pygame.Surface:
        s = pygame.Surface((sz, sz), pygame.SRCALPHA)
        skull = (230, 230, 235)
        dark = (40, 40, 44)
        pygame.draw.ellipse(s, skull, (int(sz*0.15), int(sz*0.12), int(sz*0.70), int(sz*0.62)))
        # Eyes
        pygame.draw.ellipse(s, dark, (int(sz*0.30), int(sz*0.34), int(sz*0.14), int(sz*0.16)))
        pygame.draw.ellipse(s, dark, (int(sz*0.56), int(sz*0.34), int(sz*0.14), int(sz*0.16)))
        # Nose
        pygame.draw.polygon(s, dark, [(int(sz*0.50), int(sz*0.50)), (int(sz*0.46), int(sz*0.60)), (int(sz*0.54), int(sz*0.60))])
        # Teeth row
        pygame.draw.rect(s, skull, (int(sz*0.26), int(sz*0.68), int(sz*0.48), int(sz*0.08)))
        for i in range(6):
            x = int(sz*0.28 + i*sz*0.07)
            pygame.draw.line(s, dark, (x, int(sz*0.68)), (x, int(sz*0.76)), 1)
        return s.convert_alpha()

    def _draw_bat_sprite(self, sz: int) -> pygame.Surface:
        s = pygame.Surface((sz, sz), pygame.SRCALPHA)
        body = (110, 60, 140)
        dark = (20, 12, 24)
        # Body
        pygame.draw.ellipse(s, body, (int(sz*0.40), int(sz*0.40), int(sz*0.20), int(sz*0.18)))
        # Wings
        pygame.draw.polygon(s, body, [(int(sz*0.50), int(sz*0.46)), (int(sz*0.20), int(sz*0.58)), (int(sz*0.10), int(sz*0.46))])
        pygame.draw.polygon(s, body, [(int(sz*0.50), int(sz*0.46)), (int(sz*0.80), int(sz*0.58)), (int(sz*0.90), int(sz*0.46))])
        # Head
        pygame.draw.circle(s, body, (int(sz*0.50), int(sz*0.38)), max(2, sz//16))
        # Eyes
        pygame.draw.circle(s, (240, 240, 250), (int(sz*0.48), int(sz*0.38)), max(1, sz//40))
        pygame.draw.circle(s, (240, 240, 250), (int(sz*0.52), int(sz*0.38)), max(1, sz//40))
        # Outline hint
        pygame.draw.ellipse(s, dark, (int(sz*0.40), int(sz*0.40), int(sz*0.20), int(sz*0.18)), 1)
        return s.convert_alpha()

    def _process_hold(self, dt: float) -> None:
        if self.menu_open or self.map_open:
            # Do not process movement while UI is open
            for st in self._hold_state.values():
                st["was_down"] = False
                st["acc"] = 0.0
            return
        keys = pygame.key.get_pressed()

        def update(action: str, down: bool, do_step, delay: float, rate: float) -> None:
            st = self._hold_state[action]
            if down:
                if not st["was_down"]:
                    st["was_down"] = True
                    st["acc"] = -delay
                else:
                    st["acc"] += dt
                    while st["acc"] >= rate:
                        do_step()
                        st["acc"] -= rate
            else:
                st["was_down"] = False
                st["acc"] = 0.0

        # Mapping: W/Up forward, S/Down back, A/Left turn left, D/Right turn right
        update(
            "forward",
            keys[pygame.K_w] or keys[pygame.K_UP],
            self.dungeon.step_forward,
            self._hold_repeat_delay_move,
            self._hold_repeat_rate_move,
        )
        update(
            "back",
            keys[pygame.K_s] or keys[pygame.K_DOWN],
            self.dungeon.step_back,
            self._hold_repeat_delay_move,
            self._hold_repeat_rate_move,
        )
        update(
            "turn_left",
            keys[pygame.K_a] or keys[pygame.K_LEFT],
            self.dungeon.turn_left,
            self._hold_repeat_delay_turn,
            self._hold_repeat_rate_turn,
        )
        update(
            "turn_right",
            keys[pygame.K_d] or keys[pygame.K_RIGHT],
            self.dungeon.turn_right,
            self._hold_repeat_delay_turn,
            self._hold_repeat_rate_turn,
        )

    def _fog_params(self, d: int, layers: int) -> tuple[float, float]:
        if not self.fog_enabled or layers <= 1:
            return 1.0, 1.0
        # Start fog no nearer than fog_min_start, and in the last fog_layers
        start = max(self.fog_min_start, layers - self.fog_layers)
        if d <= start:
            return 1.0, 1.0
        span = max(1, self.fog_layers - 1)
        t = min(1.0, (d - start) / span)
        brightness = 1.0 - t * (1.0 - self.fog_far)
        alpha = 1.0 - t * (1.0 - self.fog_alpha_far)
        return brightness, alpha

    def _in_fog_zone(self, d: int, layers: int) -> bool:
        if not self.fog_enabled:
            return False
        start = max(self.fog_min_start, layers - self.fog_layers)
        return d >= start

    def _draw_fog_overlays(self, layers: int) -> None:
        if not self.fog_enabled or layers <= 1:
            return
        start = max(self.fog_min_start, layers - self.fog_layers)
        # Do not overlay nearer than the front hit
        nearest = self._nearest_front if self._nearest_front is not None else -1
        for d in range(max(start, nearest + 1), layers):
            fx1, fy1, fx2, fy2 = self._front_rect(d)
            rect = pygame.Rect(fx1, fy1, fx2 - fx1, fy2 - fy1)
            # Compute overlay alpha per ring
            span = max(1, self.fog_layers - 1)
            t = min(1.0, max(0.0, (d - start) / span))
            a = int(255 * (t * self.fog_overlay_alpha_far))
            if a <= 0:
                continue
            ring = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
            ring.fill((0, 0, 0, a))
            # punch inner hole for next-nearer rectangle
            if d > 0:
                inx1, iny1, inx2, iny2 = self._front_rect(d - 1)
                inner = pygame.Rect(inx1 - fx1, iny1 - fy1, (inx2 - inx1), (iny2 - iny1))
                if inner.width > 0 and inner.height > 0:
                    pygame.draw.rect(ring, (0, 0, 0, 0), inner)
            self.screen.blit(ring, rect.topleft)

    def _geom_depth_limit(self) -> int:
        # Find largest d such that the rectangle still has drawable area
        # Avoid infinite depth by capping to a reasonable number of tiles.
        max_d = 256
        last_d = 1
        for d in range(1, max_d + 1):
            x1, y1, x2, y2 = self._front_rect(d)
            if (x2 - x1) <= 2 or (y2 - y1) <= 2:
                break
            last_d = d
        return last_d

    def _update_tuning_held(self, dt: float) -> None:
        keys = pygame.key.get_pressed()
        changed = False
        # Far X: [ decrease, ] increase
        if keys[pygame.K_LEFTBRACKET]:
            self._acc_far_x_dec += self._spd_far_x * dt
            steps = int(self._acc_far_x_dec)
            if steps:
                self.margins_x[-1] -= steps
                self._acc_far_x_dec -= steps
                changed = True
        else:
            self._acc_far_x_dec = 0.0
        if keys[pygame.K_RIGHTBRACKET]:
            self._acc_far_x_inc += self._spd_far_x * dt
            steps = int(self._acc_far_x_inc)
            if steps:
                self.margins_x[-1] += steps
                self._acc_far_x_inc -= steps
                changed = True
        else:
            self._acc_far_x_inc = 0.0

        # Far Y: ; increase margin (shorter), ' decrease margin (taller)
        if keys[pygame.K_SEMICOLON]:
            self._acc_far_y_inc += self._spd_far_y * dt
            steps = int(self._acc_far_y_inc)
            if steps:
                self.margins_y[-1] += steps
                self._acc_far_y_inc -= steps
                changed = True
        else:
            self._acc_far_y_inc = 0.0
        if keys[pygame.K_QUOTE]:
            self._acc_far_y_dec += self._spd_far_y * dt
            steps = int(self._acc_far_y_dec)
            if steps:
                self.margins_y[-1] -= steps
                self._acc_far_y_dec -= steps
                changed = True
        else:
            self._acc_far_y_dec = 0.0

        # Near X: , decrease inset, . increase inset
        if keys[pygame.K_COMMA]:
            self._acc_near_x_dec += self._spd_near_x * dt
            steps = int(self._acc_near_x_dec)
            if steps:
                self.margins_x[0] = max(0, self.margins_x[0] - steps)
                self._acc_near_x_dec -= steps
                changed = True
        else:
            self._acc_near_x_dec = 0.0
        if keys[pygame.K_PERIOD]:
            self._acc_near_x_inc += self._spd_near_x * dt
            steps = int(self._acc_near_x_inc)
            if steps:
                self.margins_x[0] = min(self.width // 4, self.margins_x[0] + steps)
                self._acc_near_x_inc -= steps
                changed = True
        else:
            self._acc_near_x_inc = 0.0

        # Near Y: / increase inset (we don't implement decrease to keep controls simple)
        if keys[pygame.K_SLASH]:
            self._acc_near_y_inc += self._spd_near_y * dt
            steps = int(self._acc_near_y_inc)
            if steps:
                self.margins_y[0] = min(self.height // 4, self.margins_y[0] + steps)
                self._acc_near_y_inc -= steps
                changed = True
        else:
            self._acc_near_y_inc = 0.0

        # Layers: - decrease, = increase
        if keys[pygame.K_MINUS]:
            self._acc_layer_dec += self._rate_layers * dt
            steps = int(self._acc_layer_dec)
            if steps:
                self.layers = max(4, self.layers - steps)
                self._acc_layer_dec -= steps
                changed = True
        else:
            self._acc_layer_dec = 0.0
        if keys[pygame.K_EQUALS]:
            self._acc_layer_inc += self._rate_layers * dt
            steps = int(self._acc_layer_inc)
            if steps:
                self.layers = min(32, self.layers + steps)
                self._acc_layer_inc -= steps
                changed = True
        else:
            self._acc_layer_inc = 0.0

        if changed:
            self._clamp_anchors()

    def _mx(self, d: int) -> int:
        # Vanishing-point mode: converge towards center with distance.
        if getattr(self, "use_vanishing", False):
            W = self.width
            half = W // 2 - 1
            k = max(0.01, float(self.vp_depth_x))
            t = (d) / (d + k)
            return int(half * t)
        # Anchor mode fallback
        anchors = self.margins_x
        if not anchors:
            return 0
        idx = min(max(0, d), len(anchors) - 1)
        return int(anchors[idx])

    def _my(self, d: int) -> int:
        # Vanishing-point mode: tie vertical convergence to horizontal to keep edges straight
        if getattr(self, "use_vanishing", False):
            H = self.height
            # Maintain far-end proportion to ensure straight side edges
            far_mx = max(1, self.margins_x[-1])
            far_my = max(1, self.margins_y[-1])
            r = min((H // 2 - 1) / far_mx, far_my / far_mx)
            mx = self._mx(d)
            return int(min(H // 2 - 1, r * mx))
        # Anchor mode fallback
        anchors = self.margins_y
        if not anchors:
            return 0
        idx = min(max(0, d), len(anchors) - 1)
        return int(anchors[idx])

    # ----------------- Tuning persistence & overlay -----------------
    def _clamp_anchors(self) -> None:
        # Ensure monotonic increase and reasonable bounds
        max_x = self.width // 2 - 2
        max_y = self.height // 2 - 2
        self.margins_x = [max(0, min(max_x, v)) for v in self.margins_x]
        self.margins_y = [max(0, min(max_y, v)) for v in self.margins_y]
        for i in range(1, len(self.margins_x)):
            if self.margins_x[i] < self.margins_x[i - 1]:
                self.margins_x[i] = self.margins_x[i - 1]
        for i in range(1, len(self.margins_y)):
            if self.margins_y[i] < self.margins_y[i - 1]:
                self.margins_y[i] = self.margins_y[i - 1]

    def _load_tuning(self) -> None:
        try:
            if os.path.exists(self.tuning_path):
                with open(self.tuning_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                layers = int(data.get("layers", self.layers))
                mx = data.get("margins_x")
                my = data.get("margins_y")
                if isinstance(mx, list) and len(mx) == 4:
                    self.margins_x = [int(v) for v in mx]
                if isinstance(my, list) and len(my) == 4:
                    self.margins_y = [int(v) for v in my]
                self.layers = max(4, min(32, layers))
                self._clamp_anchors()
        except Exception:
            # Ignore malformed file; keep defaults
            pass

    def _save_tuning(self) -> None:
        try:
            data = {
                "layers": self.layers,
                "margins_x": self.margins_x,
                "margins_y": self.margins_y,
            }
            with open(self.tuning_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            self._toast("Tuning saved.")
        except Exception as e:
            self._toast(f"Save failed: {e}")

    def _draw_tuning_overlay(self) -> None:
        W, H = self.width, self.height
        overlay = pygame.Surface((W, 160), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 170))
        self.screen.blit(overlay, (0, 0))
        lines = [
            f"TUNING MODE (T)  S:save  R:reset  -/+:layers ({self.layers})  L:auto-layers={'on' if self.auto_layers else 'off'}",
            f"margins_x anchors: {self.margins_x}   [ / ] alters far X   , / . near X",
            f"margins_y anchors: {self.margins_y}   ; / ' alters far Y   / near Y+",
            f"fog: last {self.fog_layers} layers, brightness floor {self.fog_far:.2f}",
        ]
        y = 10
        for line in lines:
            surf = self.font.render(line, True, self.color_text)
            self.screen.blit(surf, (10, y))
            y += 22

    # Removed dynamic perspective helpers to revert to tuned static 4-layer view
