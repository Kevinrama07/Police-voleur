"""Configuration applicative (interface et modes) — le moteur de jeu n'en dépend pas."""

from __future__ import annotations

from dataclasses import dataclass

from core.constants import (
    DEFAULT_MAX_MOVES,
    DEFAULT_REPETITION_LIMIT,
    DEFAULT_RETURN_COOLDOWN,
)

APP_TITLE = "POLICE – VOLEUR"
APP_VERSION = "1.0.0"
WINDOW_SIZE = (1280, 800)
FPS = 60

BOARD_IMAGE = "assets/images/board.png"
BOARD_REFERENCE_SIZE = (689, 796)

AI_DEFAULT_DEPTH = 4
AI_TIME_LIMIT_SECONDS = 2.0
DEMO_STEP_DELAY_SECONDS = 0.8


@dataclass
class GameSettings:
    """Paramètres modifiables depuis l'écran Paramètres (moteur : `RuleSet`)."""

    ai_depth: int = AI_DEFAULT_DEPTH
    ai_time_limit: float = AI_TIME_LIMIT_SECONDS
    demo_speed: float = 1.0
    seed: int | None = None
    return_cooldown: int = DEFAULT_RETURN_COOLDOWN
    center_contestable: bool = True
    repetition_limit: int = DEFAULT_REPETITION_LIMIT
    max_moves: int = DEFAULT_MAX_MOVES
