"""Configuration applicative : une seule source de réglages pour l'IA et les règles."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from core.constants import (
    DEFAULT_CENTER_CONTESTABLE,
    DEFAULT_MAX_MOVES,
    DEFAULT_REPETITION_LIMIT,
    DEFAULT_RETURN_COOLDOWN,
)
from core.game_manager import GameConfig
from core.ruleset import RuleSet

APP_TITLE = "POLICE – VOLEUR"
APP_VERSION = "1.0.0"
WINDOW_SIZE = (1280, 800)
FPS = 60

BOARD_IMAGE = "assets/images/board.png"
BOARD_REFERENCE_SIZE = (689, 796)

AI_DEFAULT_DEPTH = 4
AI_TIME_LIMIT_SECONDS = 2.0
DEMO_STEP_DELAY_SECONDS = 0.8


class Difficulty(str, Enum):
    """Niveaux prédéfinis ; `personnalise` indique un réglage manuel."""

    FACILE = "facile"
    NORMAL = "normal"
    DIFFICILE = "difficile"
    PERSONNALISE = "personnalise"


DIFFICULTY_PRESETS: dict[Difficulty, tuple[int, float, int]] = {
    Difficulty.FACILE: (2, 0.8, DEFAULT_RETURN_COOLDOWN + 2),
    Difficulty.NORMAL: (4, AI_TIME_LIMIT_SECONDS, DEFAULT_RETURN_COOLDOWN),
    Difficulty.DIFFICILE: (4, AI_TIME_LIMIT_SECONDS * 2, DEFAULT_RETURN_COOLDOWN - 2),
}


@dataclass
class GameSettings:
    """Réglages modifiables ; `to_game_config()` est le seul point de traduction."""

    ai_depth: int = AI_DEFAULT_DEPTH
    ai_time_limit: float = AI_TIME_LIMIT_SECONDS
    difficulty: Difficulty = Difficulty.NORMAL
    demo_speed: float = 1.0
    seed: int | None = None
    return_cooldown: int = DEFAULT_RETURN_COOLDOWN
    center_contestable: bool = DEFAULT_CENTER_CONTESTABLE
    repetition_limit: int = DEFAULT_REPETITION_LIMIT
    max_moves: int = DEFAULT_MAX_MOVES

    def apply_difficulty(self, difficulty: Difficulty | str) -> None:
        """Applique un préréglage complet de difficulté."""
        level = Difficulty(difficulty)
        self.ai_depth, self.ai_time_limit, self.return_cooldown = DIFFICULTY_PRESETS[level]
        self.difficulty = level

    def mark_custom(self) -> None:
        """Marque les réglages comme personnalisés après une modification manuelle."""
        self.difficulty = Difficulty.PERSONNALISE

    def to_rules(self) -> RuleSet:
        return RuleSet(
            return_cooldown=self.return_cooldown,
            center_contestable=self.center_contestable,
        )

    def to_game_config(self) -> GameConfig:
        return GameConfig(
            max_moves=self.max_moves,
            repetition_limit=self.repetition_limit,
            rules=self.to_rules(),
        )


def settings_to_rules(settings: GameSettings) -> RuleSet:
    """Alias de compatibilité pour les anciens appels."""
    return settings.to_rules()
