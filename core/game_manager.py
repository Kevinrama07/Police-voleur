"""Chef d'orchestre d'une partie : tours, statut, historique, répétitions."""

from __future__ import annotations

from dataclasses import dataclass

from core.constants import (
    DEFAULT_MAX_MOVES,
    DEFAULT_REPETITION_LIMIT,
    GameStatus,
)
from core.game_rules import (
    GameOverError,
    apply_move,
    legal_moves,
    outcome_after_move,
    thief_is_blocked,
)
from core.game_state import GameState, Move
from core.graph import Graph
from core.position_generator import generate_initial_state_from_seed
from core.ruleset import DEFAULT_RULES, RuleSet


@dataclass(frozen=True, slots=True)
class GameConfig:
    """Paramètres de partie ; 0 (ou négatif) désactive la règle correspondante."""

    max_moves: int = DEFAULT_MAX_MOVES
    repetition_limit: int = DEFAULT_REPETITION_LIMIT
    rules: RuleSet = DEFAULT_RULES


class GameManager:
    """Gère l'état courant, l'historique, les répétitions et le résultat."""

    def __init__(
        self,
        graph: Graph,
        config: GameConfig | None = None,
        seed: int | None = None,
        state: GameState | None = None,
    ) -> None:
        self._graph = graph
        self._config = config or GameConfig()
        self._seed = 0 if seed is None else int(seed)
        self._forced_state = state
        self.reset(None if state is not None else self._seed)

    @property
    def forced_state(self) -> GameState | None:
        return self._forced_state

    @property
    def graph(self) -> Graph:
        return self._graph

    @property
    def config(self) -> GameConfig:
        return self._config

    @property
    def seed(self) -> int:
        return self._seed

    @property
    def state(self) -> GameState:
        return self._state

    @property
    def status(self) -> GameStatus:
        return self._status

    @property
    def is_over(self) -> bool:
        return self._status is not GameStatus.ONGOING

    @property
    def history(self) -> tuple[GameState, ...]:
        return tuple(self._history)

    @property
    def move_history(self) -> tuple[Move, ...]:
        return tuple(self._moves)

    @property
    def move_count(self) -> int:
        return len(self._moves)

    @property
    def ply(self) -> int:
        """Nombre de demi-coups déjà joués (conditionne le cooldown du centre)."""
        return len(self._moves)

    @property
    def rules(self) -> RuleSet:
        return self._config.rules

    def reset(self, seed: int | None = None) -> GameState:
        if seed is not None:
            self._seed = int(seed)
        if self._forced_state is not None:
            self._state = self._forced_state
        else:
            self._state = generate_initial_state_from_seed(self._graph, self._seed)
        self._history: list[GameState] = [self._state]
        self._moves: list[Move] = []
        self._status = (
            GameStatus.POLICE_WIN
            if thief_is_blocked(self._graph, self._state, self._config.rules, 0)
            else GameStatus.ONGOING
        )
        self._occurrences: dict[tuple[str, tuple[str, str, str], str], int] = {
            self._state.position_key(): 1
        }
        return self._state

    def legal_moves(self) -> list[Move]:
        if self.is_over:
            return []
        return legal_moves(self._graph, self._state, self._config.rules, self.ply)

    def play(self, move: Move) -> GameStatus:
        """Applique un coup, met à jour le statut et retourne le statut résultant."""
        if self.is_over:
            raise GameOverError(f"partie terminée ({self._status.value})")
        previous = self._state
        ply = len(self._moves)
        state = apply_move(self._graph, previous, move, self._config.rules, ply)
        status = outcome_after_move(
            self._graph, previous, move, state, self._config.rules, ply + 1
        )

        if status is GameStatus.ONGOING:
            key = state.position_key()
            occurrences = self._occurrences.get(key, 0) + 1
            if (
                self._config.repetition_limit > 0
                and occurrences >= self._config.repetition_limit
            ):
                status = GameStatus.DRAW
            elif (
                self._config.max_moves > 0
                and len(self._moves) + 1 >= self._config.max_moves
            ):
                status = GameStatus.DRAW
            self._occurrences[key] = occurrences

        self._state = state
        self._moves.append(move)
        self._history.append(state)
        self._status = status
        return status

    def winner_text(self) -> str:
        match self._status:
            case GameStatus.POLICE_WIN:
                return "Victoire de la POLICE"
            case GameStatus.THIEF_WIN:
                return "Victoire du VOLEUR"
            case GameStatus.DRAW:
                return "Match nul"
            case _:
                return "Partie en cours"
