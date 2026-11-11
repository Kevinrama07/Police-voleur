"""Primitives géométriques du plateau (repère de l'image de référence).

Utilisées par le rendu fidèle (interface) et par les tests de fidélité.
Aucune dépendance à Pygame.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Ellipse:
    cx: float
    cy: float
    a: float
    b: float


@dataclass(frozen=True, slots=True)
class Segment:
    x1: float
    y1: float
    x2: float
    y2: float


@dataclass(frozen=True, slots=True)
class Circle:
    cx: float
    cy: float
    r: float


OUTER_ELLIPSE = Ellipse(cx=348.54, cy=408.54, a=210.43, b=218.98)

VERTICAL_LINE = Segment(x1=352.0, y1=189.6, x2=352.0, y2=627.5)
HORIZONTAL_LINE = Segment(x1=138.1, y1=406.5, x2=559.0, y2=406.5)

CENTRAL_CIRCLE = Circle(cx=352.54, cy=406.05, r=40.74)

ARC_CIRCLES: dict[str, Circle] = {
    "A1": Circle(cx=360.38, cy=202.29, r=70.99),
    "A2": Circle(cx=347.05, cy=202.21, r=70.65),
    "ALU": Circle(cx=144.03, cy=403.13, r=81.23),
    "ALL": Circle(cx=141.69, cy=417.37, r=84.49),
    "ARU": Circle(cx=553.56, cy=401.36, r=77.60),
    "ARL": Circle(cx=553.63, cy=408.91, r=77.54),
    "A6": Circle(cx=340.74, cy=620.81, r=72.08),
    "A7": Circle(cx=365.63, cy=618.66, r=69.69),
}


def ellipse_norm(x: float, y: float, ellipse: Ellipse = OUTER_ELLIPSE) -> float:
    """Distance normalisée à l'ellipse : <1 intérieur, 1 sur le contour, >1 extérieur."""
    return (
        ((x - ellipse.cx) / ellipse.a) ** 2 + ((y - ellipse.cy) / ellipse.b) ** 2
    ) ** 0.5
