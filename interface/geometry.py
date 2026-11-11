"""Transformations de coordonnées et échantillonnage des primitives du plateau.

Repère logique : image de référence 689 x 796, y vers le bas (comme `core.graph`).
Ce module ne dépend pas de Pygame afin de rester testable en isolation.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from core.board_geometry import Ellipse, OUTER_ELLIPSE

Point = tuple[float, float]


@dataclass(frozen=True, slots=True)
class ViewTransform:
    """Mise à l'échelle uniforme et translation du repère image vers l'écran."""

    scale: float
    offset_x: float
    offset_y: float

    def to_screen(self, x: float, y: float) -> Point:
        return (self.offset_x + x * self.scale, self.offset_y + y * self.scale)

    def to_board(self, sx: float, sy: float) -> Point:
        return (
            (sx - self.offset_x) / self.scale,
            (sy - self.offset_y) / self.scale,
        )


def ink_bounds(ellipse: Ellipse = OUTER_ELLIPSE, margin: float = 0.0) -> tuple[float, float, float, float]:
    """Boîte englobante du dessin (l'ellipse extérieure), avec marge optionnelle."""
    return (
        ellipse.cx - ellipse.a - margin,
        ellipse.cy - ellipse.b - margin,
        (ellipse.a + margin) * 2,
        (ellipse.b + margin) * 2,
    )


def fit_transform(
    area_width: int,
    area_height: int,
    *,
    ellipse: Ellipse = OUTER_ELLIPSE,
    margin: float = 18.0,
) -> ViewTransform:
    """Centre le dessin dans une zone écran en conservant le ratio du plateau."""
    bx, by, bw, bh = ink_bounds(ellipse, margin)
    scale = min(area_width / bw, area_height / bh)
    offset_x = (area_width - bw * scale) / 2 - bx * scale
    offset_y = (area_height - bh * scale) / 2 - by * scale
    return ViewTransform(scale=scale, offset_x=offset_x, offset_y=offset_y)


def ellipse_points(
    ellipse: Ellipse = OUTER_ELLIPSE, steps: int = 240
) -> list[Point]:
    return [
        (
            ellipse.cx + ellipse.a * math.cos(2 * math.pi * index / steps),
            ellipse.cy + ellipse.b * math.sin(2 * math.pi * index / steps),
        )
        for index in range(steps + 1)
    ]


def circle_points(center: Point, radius: float, steps: int = 160) -> list[Point]:
    cx, cy = center
    return [
        (
            cx + radius * math.cos(2 * math.pi * index / steps),
            cy + radius * math.sin(2 * math.pi * index / steps),
        )
        for index in range(steps + 1)
    ]


def arc_points(
    center: Point,
    radius: float,
    start: Point,
    end: Point,
    *,
    max_step_deg: float = 2.0,
) -> list[Point]:
    """Arc de cercle le plus court reliant deux points du cercle."""
    cx, cy = center
    a0 = math.atan2(start[1] - cy, start[0] - cx)
    a1 = math.atan2(end[1] - cy, end[0] - cx)
    delta = (a1 - a0 + math.pi) % (2 * math.pi) - math.pi
    steps = max(8, int(abs(math.degrees(delta)) / max_step_deg) + 1)
    return [
        (
            cx + radius * math.cos(a0 + delta * index / steps),
            cy + radius * math.sin(a0 + delta * index / steps),
        )
        for index in range(steps + 1)
    ]


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def lerp_point(a: Point, b: Point, t: float) -> Point:
    return (lerp(a[0], b[0], t), lerp(a[1], b[1], t))
