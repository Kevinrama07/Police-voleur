"""Minimax renforcé de la POLICE : recherche exacte aux feuilles et anti-répétition.

Le VOLEUR conserve intégralement `SearchEngine` et son évaluation heuristique. La
POLICE utilise le même algorithme Minimax/Alpha-Beta, mais ses feuilles sont notées
par la table rétrograde du jeu (`ai/police_solver.py`) et son coup racine est filtré
pour ne jamais provoquer une nulle par répétition lorsqu'une victoire est disponible.
"""

from __future__ import annotations

from dataclasses import replace

from ai.minimax import SearchConfig, SearchEngine, SearchResult
from ai.police_solver import solved_game
from core.constants import Team
from core.game_rules import apply_move
from core.game_state import GameState
from core.graph import Graph
from core.ruleset import RuleSet


def exact_evaluation(
    graph: Graph,
    state: GameState,
    ply: int,
    rules: RuleSet,
) -> int:
    solver = solved_game(graph, rules)
    return solver.map_score(solver.value(state, ply), 0)


class PoliceMinimaxEngine:
    """Moteur Minimax de la POLICE, plus fort que le Minimax historique."""

    def __init__(self, graph: Graph, config: SearchConfig | None = None) -> None:
        self.graph = graph
        self.config = config or SearchConfig()
        self.engine = SearchEngine(graph)
        self._history: tuple[GameState, ...] = ()
        self._repetition_limit = 0

    def set_context(
        self,
        history: tuple[GameState, ...] = (),
        repetition_limit: int = 0,
    ) -> None:
        self._history = tuple(history)
        self._repetition_limit = int(repetition_limit)

    def search(
        self,
        state: GameState,
        config: SearchConfig | None = None,
        ply: int = 0,
    ) -> SearchResult:
        if state.turn is not Team.POLICE:
            raise ValueError("le moteur POLICE ne traite que les tours de la police")
        cfg = replace(config or self.config, evaluator=exact_evaluation)
        result = self.engine.search(state, cfg, ply)
        return self._avoid_repetition(state, result, cfg, ply)

    def _avoid_repetition(
        self,
        state: GameState,
        result: SearchResult,
        config: SearchConfig,
        ply: int,
    ) -> SearchResult:
        if not result.root_scores or self._repetition_limit <= 0:
            return result
        counts: dict[tuple, int] = {}
        for previous in self._history:
            key = previous.position_key()
            counts[key] = counts.get(key, 0) + 1
        for entry in sorted(result.root_scores, key=lambda item: item.score, reverse=True):
            child = apply_move(self.graph, state, entry.move, config.rules, ply)
            if counts.get(child.position_key(), 0) + 1 >= self._repetition_limit:
                continue
            if entry.move == result.move:
                return result
            return replace(result, move=entry.move, score=entry.score)
        return result
