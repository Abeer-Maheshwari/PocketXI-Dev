# src/transition.py
import asyncio
import math
import time
import sys
import pygame
from src.theme import THEME

IS_WASM = sys.platform in ("emscripten", "wasi")


class TransitionManager:
    # Screen transitions, fade effects, and loading spinner
    def __init__(self, screen=None, width=None, height=None):
        self.width = 1280
        self.height = 720
        self.scale = 1.0
        self.screen = screen or pygame.display.get_surface()

        self.bg_color = THEME["bg_dark"]

        # Reusable dark overlay for alpha fades
        self.overlay = pygame.Surface((self.width, self.height))
        self.overlay.fill(self.bg_color)
        self._init_fonts()

    def _init_fonts(self):
        self.font_title = pygame.font.SysFont("Arial", 28, bold=True)
        self.font_sub = pygame.font.SysFont("Arial", 18)

    def _get_active_screen(self):
        current_screen = pygame.display.get_surface()
        if current_screen:
            self.screen = current_screen
        return self.screen

    async def fade_out(self, draw_current_fn=None, duration=0.2):
        # Fade the current screen to dark background
        screen = self._get_active_screen()
        if not screen or duration <= 0:
            return

        start_time = time.perf_counter()
        while True:
            pygame.event.pump()
            elapsed = time.perf_counter() - start_time
            progress = min(1.0, elapsed / duration)
            alpha = int(progress * 255)

            if draw_current_fn:
                draw_current_fn(execute_flip=False)
            self.overlay.set_alpha(alpha)
            screen.blit(self.overlay, (0, 0))
            pygame.display.flip()

            if progress >= 1.0:
                break
            await asyncio.sleep(0)

    async def fade_transition(self, draw_outgoing_fn, draw_incoming_fn, duration=0.25):
        # Cross-fade between two screens
        screen = self._get_active_screen()
        if not screen or duration <= 0:
            if draw_incoming_fn:
                draw_incoming_fn(execute_flip=True)
            return

        half_duration = duration / 2.0

        # Phase 1: Fade out old screen
        start_time = time.perf_counter()
        while True:
            pygame.event.pump()
            elapsed = time.perf_counter() - start_time
            progress = min(1.0, elapsed / half_duration)
            alpha = int(progress * 255)

            if draw_outgoing_fn:
                draw_outgoing_fn(execute_flip=False)
            self.overlay.set_alpha(alpha)
            screen.blit(self.overlay, (0, 0))
            pygame.display.flip()

            if progress >= 1.0:
                break
            await asyncio.sleep(0)

        # Phase 2: Fade in new screen
        start_time = time.perf_counter()
        while True:
            pygame.event.pump()
            elapsed = time.perf_counter() - start_time
            progress = min(1.0, elapsed / half_duration)
            alpha = int((1.0 - progress) * 255)

            if draw_incoming_fn:
                draw_incoming_fn(execute_flip=False)
            self.overlay.set_alpha(alpha)
            screen.blit(self.overlay, (0, 0))
            pygame.display.flip()

            if progress >= 1.0:
                break
            await asyncio.sleep(0)

    async def show_loading(self, title="ENTERING PITCH...", subtitle="Setting up match", min_duration=0.45):
        # Animated loading spinner with status text
        screen = self._get_active_screen()
        if not screen:
            return

        start_time = time.perf_counter()
        spinner_radius = int(24 * self.scale)
        cx = self.width // 2
        cy = self.height // 2 - int(25 * self.scale)

        while True:
            pygame.event.pump()
            elapsed = time.perf_counter() - start_time
            if elapsed >= min_duration:
                break

            screen.fill(self.bg_color)

            # Draw rotating spinner dots
            angle = (elapsed * 360 * 1.5) % 360
            for dot_idx in range(6):
                dot_angle = math.radians(angle + (dot_idx * 25))
                x = cx + int(math.cos(dot_angle) * spinner_radius)
                y = cy + int(math.sin(dot_angle) * spinner_radius)

                color = THEME["team_home"] if dot_idx == 5 else THEME["border"]
                dot_size = max(2, int((3 + (dot_idx // 2)) * self.scale))
                pygame.draw.circle(screen, color, (x, y), dot_size)

            title_surf = self.font_title.render(title, True, THEME["text_primary"])
            sub_surf = self.font_sub.render(subtitle, True, THEME["text_muted"])

            screen.blit(title_surf, title_surf.get_rect(center=(cx, self.height // 2 + int(35 * self.scale))))
            screen.blit(sub_surf, sub_surf.get_rect(center=(cx, self.height // 2 + int(70 * self.scale))))

            pygame.display.flip()
            await asyncio.sleep(0)