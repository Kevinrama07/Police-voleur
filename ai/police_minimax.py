"""Minimax court et parfait de la POLICE (maximizer)."""

from __future__ import annotations

from dataclasses import replace

from ai.minimax import SearchConfig, SearchEngine, SearchResult, exact_evaluation
from core.constants import Team
from core.game_rules import apply_move
from core.game_state import GameState
from core.graph import Graph


class PoliceMinimaxEngine(SearchEngine):
    """Même minimax court, avec filtre anti-répétition pour ne pas gâcher un gain."""

    def __init__(self, graph: Graph, config: SearchConfig | None = None) -> None:
        super().__init__(graph)
        self.config = config or SearchConfig()
        self.history: tuple[GameState, ...] = ()
        self.repetition_limit = 0

    def set_context(
        self, history: tuple[GameState, ...] = (), repetition_limit: int = 0
    ) -> None:
        self.history, self.repetition_limit = tuple(history), int(repetition_limit)

    def search(
        self, state: GameState, config: SearchConfig | None = None, ply: int = 0
    ) -> SearchResult:
        if state.turn is not Team.POLICE:
            raise ValueError("le moteur POLICE ne traite que les tours de la police")
        cfg = replace(config or self.config, evaluator=exact_evaluation)
        result = super().search(state, cfg, ply)
        if not result.root_scores or self.repetition_limit <= 0:
            return result
        counts: dict[tuple, int] = {}
        for previous in self.history:
            counts[previous.position_key()] = counts.get(previous.position_key(), 0) + 1
        for entry in sorted(result.root_scores, key=lambda item: item.score, reverse=True):
            child = apply_move(self.graph, state, entry.move, cfg.rules, ply)
            if counts.get(child.position_key(), 0) + 1 >= self.repetition_limit:
                continue
            if entry.move == result.move:
                return result
            return replace(result, move=entry.move, score=entry.score)
        return result


__all__ = ["PoliceMinimaxEngine", "exact_evaluation"]
