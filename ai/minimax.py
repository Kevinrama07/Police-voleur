"""Minimax avec élagage Alpha-Beta, table de transposition et approfondissement itératif.

Conventions :
- la POLICE est le maximizer, le VOLEUR le minimizer ;
- `apply_move` bascule toujours le tour, donc la profondeur décroît d'un coup ;
- les scores terminaux (±10 000) sont fixés et prioritaires sur l'heuristique ;
- la recherche ignore les nulles par répétition (pas d'historique dans l'arbre) :
  le gestionnaire de partie reste seul juge des nulles ;
- `ply` (demi-coups déjà joués) est propagé pour appliquer le cooldown de retour
  au centre (`RuleSet`) ; la table de transposition inclut ce cooldown relatif.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from ai.evaluation import evaluate
from core.constants import (
    CENTER,
    POLICE_WIN_SCORE,
    THIEF_WIN_SCORE,
    Team,
)
from core.game_rules import apply_move, legal_moves, thief_is_blocked
from core.game_state import GameState, Move
from core.graph import Graph
from core.ruleset import DEFAULT_RULES, RuleSet

INFINITY = 1_000_000

EXACT = 0
LOWER = 1
UPPER = 2


class SearchTimeout(RuntimeError):
    """Limite de temps atteinte pendant la recherche."""


@dataclass(frozen=True, slots=True)
class SearchConfig:
    """Paramètres de recherche ; `time_limit=None` désactive la limite."""

    max_depth: int = 4
    time_limit: float | None = None
    alpha_beta: bool = True
    use_transposition: bool = True
    order_moves: bool = True
    record_tree: bool = False
    tree_depth: int = 2
    rules: RuleSet = DEFAULT_RULES


@dataclass(slots=True)
class SearchNode:
    """Nœud réellement exploré (visualisation pédagogique de l'arbre Minimax)."""

    state: GameState
    move: Move | None
    depth: int
    maximizing: bool
    score: int = 0
    cutoff: bool = False
    alpha: int = -INFINITY
    beta: int = INFINITY
    children: list["SearchNode"] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class MoveEvaluation:
    """Score exact d'un coup racine (panneau de démonstration)."""

    move: Move
    score: int


@dataclass(frozen=True, slots=True)
class SearchResult:
    move: Move | None
    score: int
    depth: int
    completed: bool
    nodes: int
    cutoffs: int
    tt_hits: int
    elapsed: float
    root_scores: tuple[MoveEvaluation, ...] = ()
    tree: SearchNode | None = None


@dataclass(slots=True)
class _TranspositionEntry:
    depth: int
    score: int
    flag: int
    best: Move | None


@dataclass(slots=True)
class _Context:
    graph: Graph
    config: SearchConfig
    deadline: float | None
    transposition: dict[tuple, _TranspositionEntry]
    nodes: int = 0
    cutoffs: int = 0
    tt_hits: int = 0
    _counter: int = 0

    def check_time(self) -> None:
        self._counter += 1
        if (
            self.deadline is not None
            and self._counter & 0x3FF == 0
            and time.perf_counter() >= self.deadline
        ):
            raise SearchTimeout


class SearchEngine:
    """Moteur de recherche réutilisable ; précalcule les distances statiques."""

    def __init__(self, graph: Graph) -> None:
        self.graph = graph
        self._static = {vertex: graph.bfs_distances(vertex) for vertex in graph}

    def order_moves(self, state: GameState, moves: list[Move]) -> list[Move]:
        """Ordonne les coups pour améliorer l'élagage.

        Policiers : d'abord les coups qui rapprochent un policier du voleur.
        Voleur : d'abord les coups qui rapprochent du centre.
        """
        distances = self._static
        if state.turn is Team.THIEF:
            return sorted(
                moves,
                key=lambda m: (distances[m.dst].get(CENTER, INFINITY), m.dst),
            )
        return sorted(
            moves,
            key=lambda m: (distances[m.dst].get(state.thief, INFINITY), m.dst),
        )

    def value_full(self, state: GameState, depth: int, ply: int = 0) -> tuple[int, int]:
        """Valeur Minimax pure (aucun élagage, aucune table, aucun ordonnancement).

        Sert de référence aux tests d'équivalence Alpha-Beta.
        """
        ctx = _Context(
            graph=self.graph,
            config=SearchConfig(
                max_depth=depth,
                alpha_beta=False,
                use_transposition=False,
                order_moves=False,
            ),
            deadline=None,
            transposition={},
        )
        value = self._minimax(
            ctx,
            state,
            depth,
            -INFINITY,
            INFINITY,
            record_left=-1,
            prune=False,
            ply=ply,
        )[0]
        return value, ctx.nodes

    def search(
        self,
        state: GameState,
        config: SearchConfig | None = None,
        ply: int = 0,
    ) -> SearchResult:
        """Approfondissement itératif avec limite de temps optionnelle."""
        cfg = config or SearchConfig()
        root_moves = legal_moves(self.graph, state, cfg.rules, ply)
        start = time.perf_counter()
        if not root_moves:
            return SearchResult(
                move=None,
                score=evaluate(self.graph, state, ply, cfg.rules),
                depth=0,
                completed=True,
                nodes=0,
                cutoffs=0,
                tt_hits=0,
                elapsed=time.perf_counter() - start,
            )
        ctx = _Context(
            graph=self.graph,
            config=cfg,
            deadline=(start + cfg.time_limit) if cfg.time_limit else None,
            transposition={},
        )
        ordered_root = self.order_moves(state, root_moves) if cfg.order_moves else root_moves

        best_move: Move = ordered_root[0]
        best_score = evaluate(self.graph, state, ply, cfg.rules)
        best_depth = 0
        root_scores: tuple[MoveEvaluation, ...] = ()
        best_tree: SearchNode | None = None
        completed = False

        for depth in range(1, max(1, cfg.max_depth) + 1):
            try:
                move, score, scores, tree = self._search_root(
                    ctx, state, depth, ordered_root, ply
                )
            except SearchTimeout:
                break
            best_move, best_score, best_depth = move, score, depth
            root_scores = tuple(scores)
            best_tree = tree
            completed = depth >= cfg.max_depth

        return SearchResult(
            move=best_move,
            score=best_score,
            depth=best_depth,
            completed=completed,
            nodes=ctx.nodes,
            cutoffs=ctx.cutoffs,
            tt_hits=ctx.tt_hits,
            elapsed=time.perf_counter() - start,
            root_scores=root_scores,
            tree=best_tree,
        )

    # ------------------------------------------------------------------ internals

    @staticmethod
    def _tt_key(state: GameState, ply: int, rules: RuleSet) -> tuple:
        """Clé de transposition : la position + l'état du cooldown (écrêté)."""
        return state.position_key() + (min(ply, max(0, rules.return_cooldown)),)

    def _search_root(
        self,
        ctx: _Context,
        state: GameState,
        depth: int,
        ordered_root: list[Move],
        ply: int,
    ) -> tuple[Move, int, list[MoveEvaluation], SearchNode | None]:
        maximizing = state.turn is Team.POLICE
        record_left = ctx.config.tree_depth if ctx.config.record_tree else -1
        rules = ctx.config.rules
        root_node = (
            SearchNode(
                state=state,
                move=None,
                depth=depth,
                maximizing=maximizing,
            )
            if record_left >= 0
            else None
        )
        best_move = ordered_root[0]
        best_score = -INFINITY if maximizing else INFINITY
        scores: list[MoveEvaluation] = []

        for move in ordered_root:
            ctx.check_time()
            child_ply = ply + 1
            child_state = apply_move(ctx.graph, state, move, rules, ply)
            terminal = self._terminal_value(move, child_state, child_ply, rules)
            child_node = None
            if terminal is not None:
                value = terminal
                if root_node is not None:
                    child_node = SearchNode(
                        state=child_state,
                        move=move,
                        depth=depth - 1,
                        maximizing=not maximizing,
                        score=value,
                    )
            else:
                value, child_node = self._minimax(
                    ctx,
                    child_state,
                    depth - 1,
                    -INFINITY,
                    INFINITY,
                    record_left=record_left - 1,
                    prune=ctx.config.alpha_beta,
                    ply=child_ply,
                    node_move=move,
                    node_depth=depth - 1,
                    node_maximizing=not maximizing,
                )
            scores.append(MoveEvaluation(move, value))
            if root_node is not None and child_node is not None:
                root_node.children.append(child_node)
            if maximizing:
                if value > best_score:
                    best_score, best_move = value, move
            else:
                if value < best_score:
                    best_score, best_move = value, move
        if root_node is not None:
            root_node.score = best_score
            root_node.alpha = best_score
        return best_move, int(best_score), scores, root_node

    def _terminal_value(
        self,
        move: Move,
        child_state: GameState,
        child_ply: int,
        rules: RuleSet,
    ) -> int | None:
        if move.team is Team.THIEF and move.dst == CENTER:
            return THIEF_WIN_SCORE
        if thief_is_blocked(self.graph, child_state, rules, child_ply):
            return POLICE_WIN_SCORE
        return None

    def _minimax(
        self,
        ctx: _Context,
        state: GameState,
        depth: int,
        alpha: int,
        beta: int,
        record_left: int,
        prune: bool,
        ply: int,
        node_move: Move | None = None,
        node_depth: int | None = None,
        node_maximizing: bool | None = None,
    ) -> tuple[int, SearchNode | None]:
        ctx.nodes += 1
        ctx.check_time()

        maximizing = state.turn is Team.POLICE
        node: SearchNode | None = None
        if record_left >= 0:
            node = SearchNode(
                state=state,
                move=node_move,
                depth=depth if node_depth is None else node_depth,
                maximizing=maximizing if node_maximizing is None else node_maximizing,
            )

        if depth <= 0:
            value = evaluate(ctx.graph, state, ply, ctx.config.rules)
            if node is not None:
                node.score = value
            return value, node

        key = self._tt_key(state, ply, ctx.config.rules)
        if ctx.config.use_transposition:
            entry = ctx.transposition.get(key)
            if entry is not None and entry.depth >= depth:
                ctx.tt_hits += 1
                if entry.flag == EXACT:
                    if node is not None:
                        node.score = entry.score
                    return entry.score, node
                if entry.flag == LOWER:
                    alpha = max(alpha, entry.score)
                else:
                    beta = min(beta, entry.score)
                if alpha >= beta:
                    if node is not None:
                        node.score = entry.score
                    return entry.score, node

        moves = legal_moves(ctx.graph, state, ctx.config.rules, ply)
        if not moves:
            value = (
                POLICE_WIN_SCORE
                if state.turn is Team.THIEF
                else evaluate(ctx.graph, state, ply, ctx.config.rules)
            )
            if node is not None:
                node.score = value
            return value, node

        if ctx.config.order_moves:
            moves = self.order_moves(state, moves)

        original_alpha, original_beta = alpha, beta
        best = -INFINITY if maximizing else INFINITY
        best_move: Move | None = None

        for move in moves:
            child_ply = ply + 1
            child_state = apply_move(ctx.graph, state, move, ctx.config.rules, ply)
            terminal = self._terminal_value(
                move, child_state, child_ply, ctx.config.rules
            )
            child_node: SearchNode | None = None
            if terminal is not None:
                value = terminal
                if record_left >= 1:
                    child_node = SearchNode(
                        state=child_state,
                        move=move,
                        depth=depth - 1,
                        maximizing=not maximizing,
                        score=value,
                    )
            else:
                value, child_node = self._minimax(
                    ctx,
                    child_state,
                    depth - 1,
                    alpha,
                    beta,
                    record_left=record_left - 1,
                    prune=prune,
                    ply=child_ply,
                    node_move=move,
                    node_depth=depth - 1,
                    node_maximizing=not maximizing,
                )
            if node is not None and child_node is not None:
                node.children.append(child_node)

            if maximizing:
                if value > best:
                    best, best_move = value, move
                alpha = max(alpha, best)
            else:
                if value < best:
                    best, best_move = value, move
                beta = min(beta, best)

            if prune and alpha >= beta:
                ctx.cutoffs += 1
                if node is not None:
                    node.cutoff = True
                break

        if ctx.config.use_transposition:
            flag = EXACT
            if best <= original_alpha:
                flag = UPPER
            elif best >= original_beta:
                flag = LOWER
            existing = ctx.transposition.get(key)
            if existing is None or existing.depth <= depth:
                ctx.transposition[key] = _TranspositionEntry(depth, best, flag, best_move)

        if node is not None:
            node.score = int(best)
            node.alpha, node.beta = original_alpha, original_beta
        return int(best), node


def choose_move(
    graph: Graph,
    state: GameState,
    config: SearchConfig | None = None,
    ply: int = 0,
) -> SearchResult:
    """Raccourci : crée un moteur, cherche, retourne le résultat complet."""
    return SearchEngine(graph).search(state, config, ply)
