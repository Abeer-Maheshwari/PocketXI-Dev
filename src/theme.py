# src/theme.py
import os
import pygame
import pygame.freetype

if not pygame.get_init():
    pygame.init()
if not pygame.freetype.get_init():
    pygame.freetype.init()

# Game and menu color palette
THEME = {
    # Menu colors
    "bg_dark": (20, 30, 32),
    "card_bg": (33, 49, 51),
    "card_border": (50, 75, 78),
    "input_bg": (25, 38, 39),
    "secondary": (65, 97, 101),

    # Accent and button colors
    "primary": (112, 145, 118),
    "border": (112, 145, 118),
    "border_highlight": (142, 178, 149),
    "notification": (112, 145, 118),

    # Pitch and gameplay colors
    "pitch": (33, 49, 51),
    "lines": (242, 208, 164),
    "ball": (242, 208, 164),
    "team_home": (146, 94, 120),  # P1
    "team_away": (160, 113, 120),  # P2
    "danger": (146, 94, 120),

    # Text colors
    "text_primary": (242, 208, 164),
    "text_muted": (170, 158, 146),
}

FONT_FILES = {
    11: "font-9.ttf",
    16: "font-14.ttf",
    26: "font-24.ttf",
    40: "font-36.ttf",
    68: "font-60.ttf",
}

HUD_FONT_FILES = {
    16: "hud-14.ttf",
    26: "hud-24.ttf",
    40: "hud-36.ttf",
    68: "hud-60.ttf",
}

_FONT_CACHE = {}
_HUD_CACHE = {}


class SharpFontWrapper:
    # Font wrapper using FreeType for sharp text rendering
    def __init__(self, ft_font, size):
        self.ft = ft_font
        self.size = size

    def render(self, text, antialias=True, fgcolor=(242, 208, 164), bgcolor=None):
        if not text:
            return pygame.Surface((1, 1), pygame.SRCALPHA)

        fg = pygame.Color(fgcolor) if isinstance(fgcolor, str) else fgcolor
        bg = pygame.Color(bgcolor) if isinstance(bgcolor, str) else bgcolor

        surf, _ = self.ft.render(
            text=text,
            fgcolor=fg,
            bgcolor=bg,
            size=self.size,
        )
        return surf

    def size(self, text):
        return self.ft.get_rect(text, size=self.size).size

    def get_height(self):
        return self.ft.get_sized_height(self.size)


def get_font(size):
    # Load and cache general UI fonts
    if size in _FONT_CACHE:
        return _FONT_CACHE[size]

    closest_size = min(FONT_FILES.keys(), key=lambda s: abs(s - size))
    font_path = os.path.join("assets", "fonts", FONT_FILES[closest_size])

    ft_obj = None
    if os.path.exists(font_path):
        try:
            ft_obj = pygame.freetype.Font(font_path, size=size)
        except Exception:
            ft_obj = None

    if ft_obj is None:
        serif_stack = "Georgia,Palatino,Times New Roman,serif"
        ft_obj = pygame.freetype.SysFont(serif_stack, size, bold=(size >= 26))

    if hasattr(pygame.freetype, "HINT_NORMAL"):
        ft_obj.hinting = pygame.freetype.HINT_NORMAL
    ft_obj.antialiased = True

    wrapped = SharpFontWrapper(ft_obj, size)
    _FONT_CACHE[size] = wrapped
    return wrapped


def get_hud_font(size):
    # Load and cache HUD numbers and score fonts
    if size in _HUD_CACHE:
        return _HUD_CACHE[size]

    closest_size = min(HUD_FONT_FILES.keys(), key=lambda s: abs(s - size))
    font_path = os.path.join("assets", "fonts", HUD_FONT_FILES[closest_size])

    ft_obj = None
    if os.path.exists(font_path):
        try:
            ft_obj = pygame.freetype.Font(font_path, size=size)
        except Exception:
            ft_obj = None

    if ft_obj is None:
        sans_stack = "Trebuchet MS,Helvetica Neue,Arial,sans-serif"
        ft_obj = pygame.freetype.SysFont(sans_stack, size, bold=True)

    if hasattr(pygame.freetype, "HINT_NORMAL"):
        ft_obj.hinting = pygame.freetype.HINT_NORMAL
    ft_obj.antialiased = True

    wrapped = SharpFontWrapper(ft_obj, size)
    _HUD_CACHE[size] = wrapped
    return wrapped