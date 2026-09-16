# src/transition.py
import asyncio
import math
import time
import pygame
from src.theme import THEME


class TransitionManager:
    """Handles screen fades and loading animations scaled to the active window."""

    def __init__(self, screen=None, width=None, height=None):
        self.screen = screen or pygame.display.get_surface()
        if self.screen:
            sw, sh = self.screen.get_size()
            self.width = width or sw
            self.height = height or sh
        else:
            self.width = width or 1280
            self.height = height or 720

        self.scale = self.height / 720.0
        self.bg_color = THEME["bg_dark"]

        # Overlay surface for screen fades
        self.overlay = pygame.Surface((self.width, self.height))
        self.overlay.fill(self.bg_color)
        self._init_fonts()

    def _init_fonts(self):
        """Scales loading screen font sizes to window resolution."""
        self.scale = self.height / 720.0
        title_size = max(18, int(28 * self.scale))
        sub_size = max(12, int(18 * self.scale))
        self.font_title = pygame.font.SysFont("Arial", title_size, bold=True)
        self.font_sub = pygame.font.SysFont("Arial", sub_size)

    def _get_active_screen(self):
        """Checks if the window resolution changed and updates overlay surfaces."""
        current_screen = pygame.display.get_surface()
        if current_screen:
            self.screen = current_screen
            cw, ch = self.screen.get_size()
            if cw != self.width or ch != self.height:
                self.width = cw
                self.height = ch
                self.overlay = pygame.Surface((self.width, self.height))
                self.overlay.fill(self.bg_color)
                self._init_fonts()
        return self.screen

    async def fade_out(self, duration=0.35):
        """Fades current screen to black."""
        screen = self._get_active_screen()
        if not screen or duration <= 0:
            return

        snapshot = screen.copy()
        start_time = time.perf_counter()

        while True:
            elapsed = time.perf_counter() - start_time
            progress = min(1.0, elapsed / duration)
            alpha = int(progress * 255)

            self.overlay.set_alpha(alpha)
            screen.blit(snapshot, (0, 0))
            screen.blit(self.overlay, (0, 0))
            pygame.display.flip()

            if progress >= 1.0:
                break
            await asyncio.sleep(0)

    async def fade_between_surfaces(self, surf_before, surf_after, duration=0.55):
        """Fades from an outgoing surface into an incoming surface."""
        screen = self._get_active_screen()
        if not screen or duration <= 0:
            return

        half_duration = duration / 2.0

        # Phase 1: Fade out
        start_time = time.perf_counter()
        while True:
            elapsed = time.perf_counter() - start_time
            progress = min(1.0, elapsed / half_duration)
            alpha = int(progress * 255)

            self.overlay.set_alpha(alpha)
            screen.blit(surf_before, (0, 0))
            screen.blit(self.overlay, (0, 0))
            pygame.display.flip()

            if progress >= 1.0:
                break
            await asyncio.sleep(0)

        # Phase 2: Fade in
        start_time = time.perf_counter()
        while True:
            elapsed = time.perf_counter() - start_time
            progress = min(1.0, elapsed / half_duration)
            alpha = int((1.0 - progress) * 255)

            self.overlay.set_alpha(alpha)
            screen.blit(surf_after, (0, 0))
            screen.blit(self.overlay, (0, 0))
            pygame.display.flip()

            if progress >= 1.0:
                break
            await asyncio.sleep(0)

    async def show_loading(self, title="ENTERING PITCH...", subtitle="Synchronizing match physics", min_duration=0.6):
        """Displays a circular loading spinner and centered status text."""
        screen = self._get_active_screen()
        if not screen:
            return

        start_time = time.perf_counter()
        spinner_radius = int(24 * self.scale)
        cx = self.width // 2
        cy = self.height // 2 - int(25 * self.scale)

        while True:
            elapsed = time.perf_counter() - start_time
            if elapsed >= min_duration:
                break

            screen.fill(self.bg_color)

            # Circular animated spinner
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