"""Constantes du moteur de jeu POLICE – VOLEUR (indépendantes de Pygame)."""

from __future__ import annotations

from enum import Enum

BOARD_WIDTH = 689
BOARD_HEIGHT = 796

CENTER = "CENTER"
POLICE_COUNT = 3


class Team(str, Enum):
    """Équipe devant jouer."""

    POLICE = "police"
    THIEF = "thief"

    @property
    def opponent(self) -> "Team":
        return Team.THIEF if self is Team.POLICE else Team.POLICE


class GameStatus(str, Enum):
    """État global d'une partie."""

    ONGOING = "ongoing"
    POLICE_WIN = "police_win"
    THIEF_WIN = "thief_win"
    DRAW = "draw"


POLICE_WIN_SCORE = 10000
THIEF_WIN_SCORE = -10000

DEFAULT_MAX_MOVES = 500
DEFAULT_REPETITION_LIMIT = 3
DEFAULT_RETURN_COOLDOWN = 10
