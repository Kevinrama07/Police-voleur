"""Test de fidélité : le graphe et ses primitives expliquent le dessin original."""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from core.board_geometry import (
    ARC_CIRCLES,
    CENTRAL_CIRCLE,
    HORIZONTAL_LINE,
    OUTER_ELLIPSE,
    VERTICAL_LINE,
)

IMAGE_CANDIDATES = [
    Path(__file__).resolve().parents[1] / "Sans titre.png",
    Path(__file__).resolve().parents[1] / "image-jeu.png",
    Path(__file__).resolve().parents[1] / "assets" / "images" / "board.png",
]
IMAGE_PATH = next((path for path in IMAGE_CANDIDATES if path.exists()), IMAGE_CANDIDATES[0])

pytestmark = pytest.mark.skipif(
    not IMAGE_PATH.exists(), reason="image de référence absente"
)


def primitive_cloud() -> np.ndarray:
    points: list[tuple[float, float]] = []
    steps = 1440
    for i in range(steps):
        angle = 2.0 * math.pi * i / steps
        points.append(
            (
                OUTER_ELLIPSE.cx + OUTER_ELLIPSE.a * math.cos(angle),
                OUTER_ELLIPSE.cy + OUTER_ELLIPSE.b * math.sin(angle),
            )
        )
    for circle in (CENTRAL_CIRCLE, *ARC_CIRCLES.values()):
        for i in range(720):
            angle = 2.0 * math.pi * i / 720
            points.append(
                (
                    circle.cx + circle.r * math.cos(angle),
                    circle.cy + circle.r * math.sin(angle),
                )
            )
    for x in np.arange(HORIZONTAL_LINE.x1, HORIZONTAL_LINE.x2, 1.0):
        points.append((float(x), HORIZONTAL_LINE.y1))
    for y in np.arange(VERTICAL_LINE.y1, VERTICAL_LINE.y2, 1.0):
        points.append((VERTICAL_LINE.x1, float(y)))
    return np.array(points)


def test_every_ink_pixel_is_near_a_primitive():
    gray = np.array(Image.open(IMAGE_PATH).convert("L"))
    ys, xs = np.nonzero(gray < 30)
    xs = xs.astype(float)
    ys = ys.astype(float)
    cloud = primitive_cloud()

    distances = []
    for start in range(0, len(xs), 300):
        batch = np.stack([xs[start : start + 300], ys[start : start + 300]], axis=1)
        squared = ((batch[:, None, :] - cloud[None, :, :]) ** 2).sum(axis=2)
        distances.append(np.sqrt(squared.min(axis=1)))
    distance = np.concatenate(distances)

    assert distance.mean() < 1.6, distance.mean()
    assert np.percentile(distance, 95) < 3.0
    assert distance.max() < 6.5, distance.max()


def test_ink_pixels_stay_within_board_frame():
    gray = np.array(Image.open(IMAGE_PATH).convert("L"))
    ys, xs = np.nonzero(gray < 30)
    assert xs.min() >= 130 and xs.max() <= 580
    assert ys.min() >= 180 and ys.max() <= 640
