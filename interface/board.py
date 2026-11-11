"""Rendu du plateau : dessin vectoriel fidèle, pions, mises en évidence, débogage.

Le plateau est redessiné à partir de `core.board_geometry` (mêmes primitives que
l'analyse de l'image) : aucune coordonnée de rendu n'est inventée. L'image de
référence peut être superposée en mode débogage pour vérification visuelle.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Iterable

import pygame

from core.board_geometry import (
    ARC_CIRCLES,
    CENTRAL_CIRCLE,
    HORIZONTAL_LINE,
    OUTER_ELLIPSE,
    VERTICAL_LINE,
    Circle,
)
from core.constants import CENTER, Team
from core.game_state import GameState, Move
from core.graph import Graph
from interface import theme
from interface.animations import MoveTween, ease_out_cubic, pulse
from interface.geometry import (
    ViewTransform,
    arc_points,
    circle_points,
    ellipse_points,
    fit_transform,
    ink_bounds,
)
from interface.theme import Fonts

try:  # pygame-ce fournit gfxdraw (cercles antialiasés)
    import pygame.gfxdraw as gfxdraw
except ImportError:  # pragma: no cover - repli si gfxdraw absent
    gfxdraw = None  # type: ignore[assignment]

SUPERSAMPLE = 3
LINE_WIDTH_BOARD = 2.7
ARC_STEP_DEG = 1.6


class BoardRenderer:
    """Rendu du plateau dans une zone écran donnée (aucun état de jeu modifié)."""

    def __init__(
        self,
        graph: Graph,
        area: pygame.Rect,
        fonts: Fonts,
        *,
        image_path: str | Path | None = None,
    ) -> None:
        self.graph = graph
        self.area = area
        self.fonts = fonts
        self.transform = fit_transform(area.width, area.height, margin=14.0)
        self.pawn_radius = max(9, int(self.transform.scale * 8.6))
        self._static = self._render_static()
        self._image = self._load_reference(image_path)
        self._tween: MoveTween | None = None
        self._tween_key: tuple[Team, int] | None = None
        self._clock = 0.0

    # ------------------------------------------------------------------ calibration

    @property
    def surface(self) -> pygame.Surface:
        """Plateau statique (taille de `area`), utilisable hors du rendu de partie."""
        return self._static

    # ------------------------------------------------------------------ positions

    def screen_pos(self, vertex: str) -> tuple[float, float]:
        x, y = self.graph.position(vertex)
        return self.transform.to_screen(x, y)

    def vertex_at(self, screen_pos: tuple[float, float], radius: float = 16.0) -> str | None:
        px, py = screen_pos
        best: tuple[float, str] | None = None
        for vertex in self.graph:
            x, y = self.screen_pos(vertex)
            distance = (x - px) ** 2 + (y - py) ** 2
            if distance <= radius**2 and (best is None or distance < best[0]):
                best = (distance, vertex)
        return best[1] if best else None

    # ------------------------------------------------------------------ animations

    def begin_move(self, move: Move, duration: float = 0.16) -> None:
        self._tween_key = (move.team, move.police_index if move.police_index is not None else -1)
        self._tween = MoveTween(
            self.screen_pos(move.src), self.screen_pos(move.dst), duration
        )

    def clear_animation(self) -> None:
        self._tween = None
        self._tween_key = None

    def update(self, dt: float) -> None:
        self._clock += dt
        if self._tween is not None:
            self._tween.update(dt)
            if self._tween.finished:
                self._tween = None
                self._tween_key = None

    @property
    def animating(self) -> bool:
        return self._tween is not None

    # ------------------------------------------------------------------ dessin

    def draw(
        self,
        surface: pygame.Surface,
        state: GameState,
        *,
        legal_targets: Iterable[str] = (),
        selected_vertex: str | None = None,
        hover_vertex: str | None = None,
        preview: Move | None = None,
        thinking: Team | None = None,
        cooldown_ratio: float | None = None,
        show_debug: bool = False,
        show_reference: bool = False,
    ) -> None:
        offset = self.area.topleft
        surface.blit(self._static, offset)
        if show_reference and self._image is not None:
            self._draw_reference(surface)
        if show_debug:
            self._draw_debug(surface)

        targets = set(legal_targets)
        self._draw_cooldown(surface, cooldown_ratio)
        self._draw_targets(surface, targets, hover_vertex)
        if preview is not None:
            self._draw_preview(surface, preview)
        self._draw_pawns(surface, state, thinking, selected_vertex)

    # ------------------------------------------------------------------ statique

    def _render_static(self) -> pygame.Surface:
        width, height = self.area.size
        big = pygame.Surface(
            (width * SUPERSAMPLE, height * SUPERSAMPLE), pygame.SRCALPHA
        )
        transform = fit_transform(width * SUPERSAMPLE, height * SUPERSAMPLE, margin=14.0)

        def points(vertices: Iterable[tuple[float, float]]) -> list[tuple[int, int]]:
            return [
                (round(sx), round(sy))
                for sx, sy in (transform.to_screen(x, y) for x, y in vertices)
            ]

        width_main = max(2, round(LINE_WIDTH_BOARD * transform.scale))
        width_glow = max(4, round(LINE_WIDTH_BOARD * transform.scale * 3.2))

        fill_rect = pygame.Rect(
            round(transform.to_screen(ink_bounds()[0], ink_bounds()[1])[0]),
            round(transform.to_screen(ink_bounds()[0], ink_bounds()[1])[1]),
            round(ink_bounds()[2] * transform.scale),
            round(ink_bounds()[3] * transform.scale),
        )
        mask = pygame.Surface(fill_rect.size, pygame.SRCALPHA)
        pygame.draw.ellipse(mask, (*theme.BOARD_FILL, 255), mask.get_rect())
        big.blit(mask, fill_rect.topleft)

        shapes: list[list[tuple[float, float]]] = []
        shapes.append(ellipse_points(OUTER_ELLIPSE))
        shapes.append(circle_points((CENTRAL_CIRCLE.cx, CENTRAL_CIRCLE.cy), CENTRAL_CIRCLE.r))
        shapes.append(
            [
                (VERTICAL_LINE.x1, VERTICAL_LINE.y1),
                (VERTICAL_LINE.x2, VERTICAL_LINE.y2),
            ]
        )
        shapes.append(
            [
                (HORIZONTAL_LINE.x1, HORIZONTAL_LINE.y1),
                (HORIZONTAL_LINE.x2, HORIZONTAL_LINE.y2),
            ]
        )
        value = list(ARC_CIRCLES.items())
        for name, arc in value:
            shapes.append(self._arc_shape(name, arc))

        for shape in shapes:
            screen = points(shape)
            pygame.draw.lines(big, (*theme.BOARD_GLOW, 40), False, screen, width_glow)
        for shape in shapes:
            screen = points(shape)
            pygame.draw.lines(big, theme.BOARD_LINE, False, screen, width_main)

        for vertex in self.graph:
            x, y = transform.to_screen(*self.graph.position(vertex))
            pygame.draw.circle(big, theme.BOARD_FILL, (round(x), round(y)), width_main)
            pygame.draw.circle(
                big, theme.BOARD_LINE_SOFT, (round(x), round(y)), width_main, max(1, width_main // 2)
            )

        return pygame.transform.smoothscale(big, (width, height))

    def _arc_shape(self, primitive: str, circle: Circle) -> list[tuple[float, float]]:
        edges = [edge for edge in self.graph.edges if edge.primitive == primitive]
        if not edges:
            return circle_points((circle.cx, circle.cy), circle.r)
        edge = edges[0]
        return arc_points(
            (circle.cx, circle.cy),
            circle.r,
            self.graph.position(edge.u),
            self.graph.position(edge.v),
            max_step_deg=ARC_STEP_DEG,
        )

    # ------------------------------------------------------------------ calques

    def _draw_reference(self, surface: pygame.Surface) -> None:
        assert self._image is not None
        bx, by, bw, bh = ink_bounds()
        sx, sy = self.transform.to_screen(bx, by)
        width = max(1, round(bw * self.transform.scale))
        height = max(1, round(bh * self.transform.scale))
        scaled = pygame.transform.smoothscale(self._image, (width, height))
        surface.blit(scaled, (round(sx), round(sy)), special_flags=pygame.BLEND_MULT)

    def _load_reference(self, image_path: str | Path | None) -> pygame.Surface | None:
        if image_path is None:
            return None
        path = Path(image_path)
        if not path.is_file():
            return None
        try:
            reference = pygame.image.load(str(path)).convert()
        except pygame.error:
            return None
        bx, by, bw, bh = ink_bounds()
        rect = pygame.Rect(round(bx), round(by), round(bw), round(bh))
        return reference.subsurface(rect.clip(reference.get_rect())).copy()

    def _draw_debug(self, surface: pygame.Surface) -> None:
        offset = self.area.topleft
        font = self.fonts.mono(12)
        for edge in self.graph.edges:
            start = self.screen_pos(edge.u)
            end = self.screen_pos(edge.v)
            pygame.draw.line(
                surface,
                (*theme.DEBUG_EDGE, 90),
                (round(start[0] + offset[0]), round(start[1] + offset[1])),
                (round(end[0] + offset[0]), round(end[1] + offset[1])),
                1,
            )
        for vertex in self.graph:
            x, y = self.screen_pos(vertex)
            x += offset[0]
            y += offset[1]
            pygame.draw.circle(surface, theme.DEBUG_VERTEX, (round(x), round(y)), 2)
            label = font.render(vertex, True, theme.DEBUG_VERTEX)
            surface.blit(label, (round(x) + 5, round(y) - 14))

    def _draw_cooldown(self, surface: pygame.Surface, ratio: float | None) -> None:
        if ratio is None:
            return
        offset = self.area.topleft
        cx, cy = self.screen_pos(CENTER)
        cx += offset[0]
        cy += offset[1]
        radius = self.pawn_radius + 9
        ratio = max(0.0, min(1.0, ratio))
        if ratio <= 0:
            return
        points = [
            (
                cx + radius * math.cos(-math.pi / 2 + ratio * 2 * math.pi * index / 72),
                cy + radius * math.sin(-math.pi / 2 + ratio * 2 * math.pi * index / 72),
            )
            for index in range(73)
        ]
        color = theme.SUCCESS if ratio >= 1 else theme.POLICE
        pygame.draw.lines(
            surface, color, False, [(round(px), round(py)) for px, py in points], 2
        )

    def _draw_targets(
        self,
        surface: pygame.Surface,
        targets: set[str],
        hover: str | None,
    ) -> None:
        offset = self.area.topleft
        glow = int(120 + 80 * pulse(0.55))
        for vertex in targets:
            x, y = self.screen_pos(vertex)
            x += offset[0]
            y += offset[1]
            radius = 6 if vertex != hover else 9
            theme.alpha_disc(surface, (round(x), round(y)), radius + 7, (*theme.POLICE, glow // 3))
            self._aa_circle(surface, x, y, radius, theme.POLICE)
            self._aa_circle(surface, x, y, radius, theme.TEXT, filled=False)

    def _draw_preview(self, surface: pygame.Surface, move: Move) -> None:
        offset = self.area.topleft
        start = self.screen_pos(move.src)
        end = self.screen_pos(move.dst)
        points = [
            (round(start[0] + offset[0]), round(start[1] + offset[1])),
            (round(end[0] + offset[0]), round(end[1] + offset[1])),
        ]
        color = theme.POLICE if move.team is Team.POLICE else theme.THIEF
        box = pygame.Rect(points[0], (1, 1)).union(pygame.Rect(points[1], (1, 1))).inflate(16, 16)
        halo = pygame.Surface(box.size, pygame.SRCALPHA)
        local = [(x - box.x, y - box.y) for x, y in points]
        pygame.draw.line(halo, (*color, 90), local[0], local[1], 10)
        surface.blit(halo, box.topleft)
        pygame.draw.line(surface, color, points[0], points[1], 3)

    def _draw_pawns(
        self,
        surface: pygame.Surface,
        state: GameState,
        thinking: Team | None,
        selected_vertex: str | None,
    ) -> None:
        offset = self.area.topleft
        entries: list[tuple[tuple[Team, int], str, tuple[int, int, int], tuple[int, int, int]]] = []
        entries.append(((Team.THIEF, -1), state.thief, theme.THIEF, theme.THIEF_DARK))
        for index, vertex in enumerate(state.police):
            entries.append(((Team.POLICE, index), vertex, theme.POLICE, theme.POLICE_DARK))

        for key, vertex, color, dark in entries:
            if self._tween is not None and self._tween_key == key:
                x, y = self._tween.position()
            else:
                x, y = self.screen_pos(vertex)
            x += offset[0]
            y += offset[1]
            active = thinking is not None and key[0] is thinking
            if active:
                ring = int(self.pawn_radius + 4 + 4 * pulse(0.7, 1.3 if key[0] is Team.THIEF else 0.0))
                glow_alpha = int(70 + 60 * pulse(0.7, 2.0))
                theme.alpha_disc(surface, (round(x), round(y)), ring + 6, (*color, glow_alpha))
                pygame.draw.circle(surface, color, (round(x), round(y)), ring, 2)
            if vertex == selected_vertex and key[0] is Team.POLICE:
                pygame.draw.circle(
                    surface, theme.TEXT, (round(x), round(y)), self.pawn_radius + 5, 2
                )
            theme.alpha_disc(surface, (round(x) + 1, round(y) + 3), self.pawn_radius, (0, 0, 0, 110))
            self._aa_circle(surface, x, y, self.pawn_radius, dark)
            self._aa_circle(surface, x, y, self.pawn_radius - 2, color)
            highlight = (min(255, color[0] + 70), min(255, color[1] + 70), min(255, color[2] + 70))
            self._aa_circle(
                surface,
                x - self.pawn_radius * 0.28,
                y - self.pawn_radius * 0.32,
                max(2, self.pawn_radius // 4),
                highlight,
            )
            self._aa_circle(surface, x, y, self.pawn_radius, theme.BG, filled=False)

    # ------------------------------------------------------------------ primitives

    def _aa_circle(
        self,
        surface: pygame.Surface,
        x: float,
        y: float,
        radius: float,
        color: tuple[int, int, int],
        *,
        filled: bool = True,
    ) -> None:
        ix, iy, ir = round(x), round(y), max(1, round(radius))
        if gfxdraw is not None:
            if filled:
                gfxdraw.filled_circle(surface, ix, iy, ir, color)
            gfxdraw.aacircle(surface, ix, iy, ir, color)
        else:  # pragma: no cover
            pygame.draw.circle(surface, color, (ix, iy), ir, 0 if filled else 1)
