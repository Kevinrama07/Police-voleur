"""Animations : tweens, pulsations et transitions d'écran (durées en secondes)."""

from __future__ import annotations

import math

from interface.geometry import Point, lerp_point


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return low if value < low else high if value > high else value


def ease_out_cubic(t: float) -> float:
    t = clamp(t)
    return 1 - (1 - t) ** 3


def ease_in_out_cubic(t: float) -> float:
    t = clamp(t)
    return 4 * t**3 if t < 0.5 else 1 - (-2 * t + 2) ** 3 / 2


def ease_out_back(t: float) -> float:
    t = clamp(t)
    c1 = 1.70158
    return 1 + (c1 + 1) * (t - 1) ** 3 + c1 * (t - 1) ** 2


def pulse(speed: float = 1.0, phase: float = 0.0) -> float:
    """Oscillation douce dans [0, 1]."""
    return 0.5 + 0.5 * math.sin(phase + speed * 2 * math.pi)


class MoveTween:
    """Interpolation d'un pion entre deux sommets (durée + easing)."""

    __slots__ = ("start", "end", "duration", "elapsed", "origin", "target")

    def __init__(
        self,
        origin: Point,
        target: Point,
        duration: float = 0.18,
        start: Point | None = None,
        end: Point | None = None,
    ) -> None:
        self.origin = origin
        self.target = target
        self.start = origin if start is None else start
        self.end = target if end is None else end
        self.duration = max(0.01, duration)
        self.elapsed = 0.0

    @property
    def finished(self) -> bool:
        return self.elapsed >= self.duration

    @property
    def progress(self) -> float:
        return clamp(self.elapsed / self.duration)

    def update(self, dt: float) -> None:
        self.elapsed += dt

    def position(self) -> Point:
        return lerp_point(self.start, self.end, ease_out_cubic(self.progress))


class Fade:
    """Volet de transition plein écran : `phase` = 'out' puis 'in'."""

    def __init__(self, duration: float = 0.16) -> None:
        self.duration = duration
        self.elapsed = 0.0
        self.phase = "out"
        self.done = False

    @property
    def alpha(self) -> int:
        return int(255 * clamp(self.elapsed / self.duration))

    def update(self, dt: float) -> None:
        self.elapsed += dt
        if self.elapsed >= self.duration:
            if self.phase == "out":
                self.phase = "in"
                self.elapsed = 0.0
            else:
                self.done = True
