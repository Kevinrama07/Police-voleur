"""Palette, typographie et primitives de style de l'interface Pygame.

Aucune règle du jeu ici : uniquement de la présentation. La palette suit la
direction artistique du prompt (bleu nuit, bleu électrique, rouge, blanc cassé, gris).
"""

from __future__ import annotations

import pygame

from config import APP_TITLE

BG = (9, 13, 24)
BG_SOFT = (13, 18, 32)
PANEL = (19, 26, 43)
PANEL_SOFT = (24, 32, 52)
PANEL_HOVER = (31, 41, 66)
STROKE = (42, 55, 86)
STROKE_SOFT = (32, 43, 69)

TEXT = (236, 240, 248)
TEXT_MUTED = (148, 160, 184)
TEXT_DIM = (99, 112, 138)

POLICE = (72, 158, 255)
POLICE_DARK = (34, 82, 146)
POLICE_GLOW = (72, 158, 255)
THIEF = (255, 92, 102)
THIEF_DARK = (150, 42, 52)
THIEF_GLOW = (255, 92, 102)

SUCCESS = (96, 216, 154)
WARNING = (255, 188, 88)
DRAW = (166, 176, 196)

BOARD_FILL = (12, 18, 31)
BOARD_LINE = (206, 214, 230)
BOARD_LINE_SOFT = (150, 162, 186)
BOARD_GLOW = (86, 132, 210)

DEBUG_VERTEX = (255, 208, 92)
DEBUG_EDGE = (92, 214, 190)

TITLE = APP_TITLE

_UI_FAMILIES = ("Segoe UI", "Calibri", "Verdana", "Arial")
_MONO_FAMILIES = ("Consolas", "Cascadia Mono", "Courier New")


class Fonts:
    """Cache de polices ; à instancier après `pygame.font.init()`."""

    def __init__(self) -> None:
        self._cache: dict[tuple[str, int, bool], pygame.font.Font] = {}

    def _get(self, families: tuple[str, ...], size: int, bold: bool) -> pygame.font.Font:
        key = (families[0], size, bold)
        font = self._cache.get(key)
        if font is None:
            path = None
            for family in families:
                path = pygame.font.match_font(family, bold=bold)
                if path:
                    break
            font = pygame.font.Font(path, size)
            font.set_bold(bold)
            self._cache[key] = font
        return font

    def ui(self, size: int, bold: bool = False) -> pygame.font.Font:
        return self._get(_UI_FAMILIES, size, bold)

    def mono(self, size: int, bold: bool = False) -> pygame.font.Font:
        return self._get(_MONO_FAMILIES, size, bold)

    def title(self, size: int = 64) -> pygame.font.Font:
        return self.ui(size, bold=True)


def text(
    surface: pygame.Surface,
    font: pygame.font.Font,
    value: str,
    pos: tuple[int, int],
    color: tuple[int, int, int] = TEXT,
    *,
    center: bool = False,
    right: bool = False,
) -> pygame.Rect:
    """Rend un texte et retourne son rectangle (alignement gauche par défaut)."""
    rendered = font.render(value, True, color)
    rect = rendered.get_rect()
    if center:
        rect.center = pos
    elif right:
        rect.topright = pos
    else:
        rect.topleft = pos
    surface.blit(rendered, rect)
    return rect


def tracking_text(
    surface: pygame.Surface,
    font: pygame.font.Font,
    value: str,
    pos: tuple[int, int],
    color: tuple[int, int, int] = TEXT_MUTED,
    tracking: int = 3,
) -> pygame.Rect:
    """Texte avec interlettrage (étiquettes en capitales)."""
    x, y = pos
    total = sum(font.size(char)[0] + tracking for char in value) - tracking
    height = font.get_height()
    for char in value:
        glyph = font.render(char, True, color)
        surface.blit(glyph, (x, y))
        x += font.size(char)[0] + tracking
    return pygame.Rect(pos[0], pos[1], total, height)


def panel(
    surface: pygame.Surface,
    rect: pygame.Rect,
    *,
    fill: tuple[int, int, int] = PANEL,
    stroke: tuple[int, int, int] | None = STROKE_SOFT,
    radius: int = 14,
    width: int = 1,
) -> None:
    pygame.draw.rect(surface, fill, rect, border_radius=radius)
    if stroke is not None:
        pygame.draw.rect(surface, stroke, rect, width=width, border_radius=radius)


def alpha_disc(
    surface: pygame.Surface,
    center: tuple[int, int],
    radius: int,
    color: tuple[int, int, int, int],
) -> None:
    """Disque translucide (glow) rendu sur une petite surface temporaire."""
    if radius <= 0:
        return
    size = radius * 2 + 2
    layer = pygame.Surface((size, size), pygame.SRCALPHA)
    pygame.draw.circle(layer, color, (size // 2, size // 2), radius)
    surface.blit(layer, (center[0] - size // 2, center[1] - size // 2))


def vignette(surface: pygame.Surface, strength: int = 120) -> None:
    """Assombrit légèrement les bords de l'écran (profondeur visuelle)."""
    width, height = surface.get_size()
    layer = pygame.Surface((width, height), pygame.SRCALPHA)
    steps = 26
    for index in range(steps):
        inset = int(index * max(width, height) / (steps * 3.2))
        alpha = int(strength * (1 - index / steps) ** 2)
        pygame.draw.rect(
            layer,
            (0, 0, 0, alpha),
            (inset, inset, width - inset * 2, height - inset * 2),
            width=max(1, height // (steps * 3)),
            border_radius=18,
        )
    surface.blit(layer, (0, 0))
