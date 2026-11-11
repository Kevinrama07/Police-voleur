"""Contrôles d'interface réutilisables : boutons, curseurs, bascules, segments."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Iterable, Sequence

import pygame

from interface import theme
from interface.animations import clamp, pulse
from interface.geometry import lerp
from interface.theme import Fonts, text


@dataclass
class Button:
    """Bouton rectangulaire avec état de survol/pression animé."""

    rect: pygame.Rect
    label: str
    hint: str = ""
    primary: bool = False
    danger: bool = False
    enabled: bool = True
    on_click: Callable[[], None] | None = None
    key: str = ""
    _hover: float = 0.0
    _press: float = 0.0
    _hovered: bool = False
    _pressed: bool = False

    def handle(self, event: pygame.event.Event) -> bool:
        if not self.enabled:
            return False
        if event.type == pygame.MOUSEMOTION:
            self._hovered = self.rect.collidepoint(event.pos)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(event.pos):
                self._pressed = True
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            if self._pressed and self.rect.collidepoint(event.pos):
                self._pressed = False
                self._hovered = True
                if self.on_click is not None:
                    self.on_click()
                    return True
            self._pressed = False
        return False

    def update(self, dt: float) -> None:
        target = 1.0 if self._hovered and self.enabled else 0.0
        self._hover = lerp(self._hover, target, clamp(dt * 12))
        target_press = 1.0 if self._pressed else 0.0
        self._press = lerp(self._press, target_press, clamp(dt * 22))

    def draw(self, surface: pygame.Surface, fonts: Fonts) -> None:
        hovered = self._hover
        offset = int(round(self._press * 1.5))
        rect = self.rect.move(0, offset)
        if not self.enabled:
            fill = theme.PANEL
            border = theme.STROKE_SOFT
            label_color = theme.TEXT_DIM
        elif self.primary:
            fill = (
                int(lerp(theme.POLICE_DARK[0], theme.POLICE[0], hovered)),
                int(lerp(theme.POLICE_DARK[1], theme.POLICE[1], hovered)),
                int(lerp(theme.POLICE_DARK[2], theme.POLICE[2], hovered)),
            )
            border = theme.POLICE
            label_color = theme.TEXT
        else:
            fill = tuple(int(lerp(theme.PANEL[i], theme.PANEL_HOVER[i], hovered)) for i in range(3))
            border = theme.STROKE if hovered < 0.5 else theme.BOARD_GLOW
            label_color = theme.TEXT if hovered > 0.05 else theme.TEXT_MUTED

        pygame.draw.rect(surface, fill, rect, border_radius=12)
        pygame.draw.rect(surface, border, rect, width=1, border_radius=12)
        if hovered > 0.02 and not self.primary:
            accent = pygame.Rect(rect.left, rect.top + 10, 3, rect.height - 20)
            pygame.draw.rect(surface, theme.POLICE, accent, border_radius=2)

        compact = rect.width < 170
        padding = 16 if compact else 24
        label = fonts.ui(17 if compact else 20, bold=True).render(self.label, True, label_color)
        surface.blit(label, label.get_rect(midleft=(rect.left + padding, rect.centery)))
        if self.hint:
            hint = fonts.ui(14).render(self.hint, True, theme.TEXT_DIM)
            surface.blit(hint, hint.get_rect(midleft=(rect.left + 24, rect.centery + 19)))
        if not compact:
            arrow = fonts.ui(18, bold=True).render("→", True, label_color)
            surface.blit(arrow, arrow.get_rect(midright=(rect.right - 22, rect.centery)))


@dataclass
class Slider:
    """Curseur numérique avec pas et formatage."""

    rect: pygame.Rect
    label: str
    minimum: float
    maximum: float
    value: float
    step: float = 0.1
    formatter: Callable[[float], str] = lambda v: f"{v:g}"
    on_change: Callable[[float], None] | None = None
    _dragging: bool = False
    _hovered: bool = False

    @property
    def track(self) -> pygame.Rect:
        return pygame.Rect(self.rect.left, self.rect.centery - 3, self.rect.width, 6)

    def _knob_x(self) -> float:
        ratio = (self.value - self.minimum) / (self.maximum - self.minimum)
        return self.track.left + ratio * self.track.width

    def _set_from_x(self, x: float) -> None:
        ratio = clamp((x - self.track.left) / max(1, self.track.width))
        raw = self.minimum + ratio * (self.maximum - self.minimum)
        stepped = round(raw / self.step) * self.step
        value = clamp(stepped, self.minimum, self.maximum)
        if abs(value - self.value) > 1e-9:
            self.value = value
            if self.on_change is not None:
                self.on_change(value)

    def handle(self, event: pygame.event.Event) -> bool:
        if event.type == pygame.MOUSEMOTION:
            self._hovered = self.track.inflate(0, 18).collidepoint(event.pos)
            if self._dragging:
                self._set_from_x(event.pos[0])
                return True
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(event.pos):
                self._dragging = True
                self._set_from_x(event.pos[0])
                return True
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            if self._dragging:
                self._dragging = False
                return True
        elif event.type == pygame.MOUSEWHEEL and self._hovered:
            self.value = clamp(self.value + event.y * self.step, self.minimum, self.maximum)
            if self.on_change is not None:
                self.on_change(self.value)
            return True
        return False

    def draw(self, surface: pygame.Surface, fonts: Fonts) -> None:
        label = fonts.ui(15).render(self.label, True, theme.TEXT_MUTED)
        surface.blit(label, label.get_rect(topleft=(self.rect.left, self.rect.top)))
        value = fonts.mono(15, bold=True).render(self.formatter(self.value), True, theme.TEXT)
        surface.blit(value, value.get_rect(topright=(self.rect.right, self.rect.top)))

        track = self.track
        pygame.draw.rect(surface, theme.STROKE_SOFT, track, border_radius=3)
        filled = pygame.Rect(track.left, track.top, max(0, round(self._knob_x() - track.left)), track.height)
        pygame.draw.rect(surface, theme.POLICE, filled, border_radius=3)
        knob = int(self._knob_x())
        pygame.draw.circle(surface, theme.TEXT, (knob, track.centery), 7)
        pygame.draw.circle(surface, theme.POLICE, (knob, track.centery), 7, 2)
        if self._hovered or self._dragging:
            pygame.draw.circle(surface, (*theme.POLICE, 60), (knob, track.centery), 11, 1)


@dataclass
class Toggle:
    """Bascule booléenne dessinée comme un interrupteur."""

    rect: pygame.Rect
    label: str
    value: bool
    description: str = ""
    on_change: Callable[[bool], None] | None = None
    _anim: float = 0.0

    def handle(self, event: pygame.event.Event) -> bool:
        if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            if self.rect.collidepoint(event.pos):
                self.value = not self.value
                if self.on_change is not None:
                    self.on_change(self.value)
                return True
        return False

    def update(self, dt: float) -> None:
        target = 1.0 if self.value else 0.0
        self._anim = lerp(self._anim, target, clamp(dt * 14))

    def draw(self, surface: pygame.Surface, fonts: Fonts) -> None:
        label = fonts.ui(15).render(self.label, True, theme.TEXT)
        surface.blit(label, (self.rect.left, self.rect.top))
        if self.description:
            description = fonts.ui(13).render(self.description, True, theme.TEXT_DIM)
            surface.blit(description, (self.rect.left, self.rect.top + 20))
        width, height = 46, 24
        switch = pygame.Rect(self.rect.right - width, self.rect.top + 2, width, height)
        fill = tuple(
            int(lerp(theme.STROKE_SOFT[i], theme.POLICE[i], self._anim)) for i in range(3)
        )
        pygame.draw.rect(surface, fill, switch, border_radius=height // 2)
        knob_x = int(lerp(switch.left + height // 2, switch.right - height // 2, self._anim))
        pygame.draw.circle(surface, theme.TEXT, (knob_x, switch.centery), height // 2 - 3)


@dataclass
class Segmented:
    """Sélecteur de choix exclusifs (ex. camp du joueur)."""

    rect: pygame.Rect
    options: Sequence[tuple[str, str]]
    value: str
    on_change: Callable[[str], None] | None = None
    _hover: str | None = None

    def handle(self, event: pygame.event.Event) -> bool:
        if event.type == pygame.MOUSEMOTION:
            self._hover = next(
                (key for key, rect in self._rects() if rect.collidepoint(event.pos)), None
            )
        if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            for key, rect in self._rects():
                if rect.collidepoint(event.pos):
                    if key != self.value:
                        self.value = key
                        if self.on_change is not None:
                            self.on_change(key)
                    return True
        return False

    def _rects(self) -> Iterable[tuple[str, pygame.Rect]]:
        width = self.rect.width // max(1, len(self.options))
        for index, (key, _label) in enumerate(self.options):
            yield key, pygame.Rect(
                self.rect.left + index * width,
                self.rect.top,
                width,
                self.rect.height,
            )

    def draw(self, surface: pygame.Surface, fonts: Fonts) -> None:
        pygame.draw.rect(surface, theme.PANEL, self.rect, border_radius=10)
        pygame.draw.rect(surface, theme.STROKE_SOFT, self.rect, width=1, border_radius=10)
        for (key, label), (_, rect) in zip(self.options, self._rects()):
            active = key == self.value
            if active:
                inner = rect.inflate(-8, -8)
                pygame.draw.rect(surface, theme.POLICE, inner, border_radius=7)
            elif self._hover == key:
                inner = rect.inflate(-8, -8)
                pygame.draw.rect(surface, theme.PANEL_HOVER, inner, border_radius=7)
            color = theme.TEXT if active else theme.TEXT_MUTED
            rendered = fonts.ui(16, bold=active).render(label, True, color)
            surface.blit(rendered, rendered.get_rect(center=rect.center))


@dataclass
class TextInput:
    """Champ de saisie simple (adresse IP, port) avec curseur clignotant."""

    rect: pygame.Rect
    value: str = ""
    placeholder: str = ""
    allowed_chars: str | None = None
    max_length: int = 64
    focused: bool = False
    on_submit: Callable[[str], None] | None = None
    _clock: float = 0.0

    def handle(self, event: pygame.event.Event) -> bool:
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self.focused = self.rect.collidepoint(event.pos)
            return self.focused
        if not self.focused or event.type != pygame.KEYDOWN:
            return False
        if event.key == pygame.K_BACKSPACE:
            self.value = self.value[:-1]
            return True
        if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            self.focused = False
            if self.on_submit is not None:
                self.on_submit(self.value)
            return True
        if event.key in (pygame.K_TAB, pygame.K_ESCAPE):
            self.focused = False
            return False
        char = event.unicode
        if not char or not char.isprintable() or not char.strip():
            return False
        if self.allowed_chars is not None and char not in self.allowed_chars:
            return False
        if len(self.value) >= self.max_length:
            return False
        self.value += char
        return True

    def update(self, dt: float) -> None:
        self._clock += dt

    def draw(self, surface: pygame.Surface, fonts: Fonts) -> None:
        pygame.draw.rect(surface, theme.PANEL, self.rect, border_radius=10)
        border = theme.POLICE if self.focused else theme.STROKE_SOFT
        pygame.draw.rect(surface, border, self.rect, width=1, border_radius=10)
        shown = self.value or self.placeholder
        color = theme.TEXT if self.value else theme.TEXT_DIM
        rendered = fonts.mono(16).render(shown, True, color)
        surface.blit(rendered, rendered.get_rect(midleft=(self.rect.left + 14, self.rect.centery)))
        if self.focused and (self._clock % 1.0) < 0.55:
            caret_x = self.rect.left + 14 + (fonts.mono(16).size(self.value)[0] if self.value else 0)
            pygame.draw.line(
                surface,
                theme.POLICE,
                (caret_x + 1, self.rect.top + 9),
                (caret_x + 1, self.rect.bottom - 9),
                2,
            )


@dataclass
class StatRow:
    """Ligne « libellé — valeur » pour les panneaux d'information."""

    label: str
    value: str = ""
    color: tuple[int, int, int] = theme.TEXT
    mono: bool = True
    _anim: float = field(default=1.0)

    def draw(self, surface: pygame.Surface, fonts: Fonts, x: int, y: int, width: int) -> int:
        label = fonts.ui(14).render(self.label, True, theme.TEXT_MUTED)
        surface.blit(label, (x, y))
        font = fonts.mono(15, bold=True) if self.mono else fonts.ui(15, bold=True)
        value = font.render(self.value, True, self.color)
        surface.blit(value, value.get_rect(topright=(x + width, y - 1)))
        return y + 24


def pill(
    surface: pygame.Surface,
    fonts: Fonts,
    value: str,
    center: tuple[int, int],
    color: tuple[int, int, int],
    *,
    filled: bool = False,
) -> pygame.Rect:
    """Étiquette arrondie (statut, rôle, tour)."""
    text_surface = fonts.ui(13, bold=True).render(value, True, theme.BG if filled else color)
    rect = text_surface.get_rect()
    padding_x, padding_y = 12, 6
    box = pygame.Rect(0, 0, rect.width + padding_x * 2, rect.height + padding_y * 2)
    box.center = center
    if filled:
        pygame.draw.rect(surface, color, box, border_radius=box.height // 2)
    else:
        layer = pygame.Surface(box.size, pygame.SRCALPHA)
        pygame.draw.rect(
            layer, (*color, 36), layer.get_rect(), border_radius=box.height // 2
        )
        pygame.draw.rect(
            layer, (*color, 150), layer.get_rect(), width=1, border_radius=box.height // 2
        )
        surface.blit(layer, box.topleft)
    surface.blit(text_surface, text_surface.get_rect(center=box.center))
    return box


def section_title(
    surface: pygame.Surface, fonts: Fonts, value: str, x: int, y: int
) -> int:
    theme.tracking_text(surface, fonts.ui(12, bold=True), value, (x, y), theme.TEXT_DIM, 2)
    return y + 26


def dots(surface: pygame.Surface, fonts: Fonts, value: str, x: int, y: int) -> int:
    return text(surface, fonts.ui(13), value, (x, y), theme.TEXT_MUTED)[0]


def thinking_dots(surface: pygame.Surface, x: int, y: int, clock: float) -> None:
    for index in range(3):
        alpha = 80 + int(120 * pulse(0.8, index * 0.9 + clock))
        theme.alpha_disc(surface, (x + index * 12, y), 4, (*theme.POLICE, alpha))
