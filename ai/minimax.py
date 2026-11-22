"""Minimax court et fort : alpha-bêta, transposition, itératif, évaluation exacte."""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field

from ai.evaluation import evaluate
from core.constants import CENTER, POLICE_WIN_SCORE, THIEF_WIN_SCORE, Team
from core.game_rules import apply_move, legal_moves, thief_is_blocked
from core.game_state import GameState, Move
from core.graph import Graph
from core.ruleset import DEFAULT_RULES, RuleSet

INF = 1_000_000
EXACT, LOWER, UPPER = 0, 1, 2
Evaluator = Callable[[Graph, GameState, int, RuleSet], int]


class SearchTimeout(RuntimeError):
    """Limite de temps atteinte."""


def exact_evaluation(g: Graph, s: GameState, ply: int, rules: RuleSet) -> int:
    """Valeur réelle du jeu ; l'heuristique ne départage que les égalités."""
    from ai.police_solver import solved_game

    solver = solved_game(g, rules)
    return solver.map_score(solver.value(s, ply), evaluate(g, s, ply, rules))


@dataclass(frozen=True, slots=True)
class SearchConfig:
    max_depth: int = 4
    time_limit: float | None = None
    alpha_beta: bool = True
    use_transposition: bool = True
    order_moves: bool = True
    record_tree: bool = False
    tree_depth: int = 2
    rules: RuleSet = DEFAULT_RULES
    evaluator: Evaluator | None = None


@dataclass(slots=True)
class SearchNode:
    state: GameState
    move: Move | None
    depth: int
    maximizing: bool
    score: int = 0
    cutoff: bool = False
    alpha: int = -INF
    beta: int = INF
    children: list[SearchNode] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class MoveEvaluation:
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
class _Entry:
    depth: int
    score: int
    flag: int
    best: Move | None


@dataclass(slots=True)
class _Ctx:
    g: Graph
    cfg: SearchConfig
    deadline: float | None
    tt: dict
    nodes: int = 0
    cutoffs: int = 0
    hits: int = 0
    ticks: int = 0
    root_ply: int = 0
    scores: list = field(default_factory=list)

    def check(self) -> None:
        self.ticks += 1
        if (self.deadline and not self.ticks & 1023
                and time.perf_counter() >= self.deadline):
            raise SearchTimeout


class SearchEngine:
    """Un seul minimax : POLICE maximise, VOLEUR minimise."""

    def __init__(self, graph: Graph) -> None:
        self.graph = graph
        self._dist = {v: graph.bfs_distances(v) for v in graph}

    def order_moves(self, state: GameState, moves: list[Move]) -> list[Move]:
        target = CENTER if state.turn is Team.THIEF else state.thief
        dist = self._dist
        return sorted(moves, key=lambda m: (dist[m.dst].get(target, INF), m.dst))

    @staticmethod
    def _ev(ctx: _Ctx, state: GameState, ply: int) -> int:
        fn = ctx.cfg.evaluator or exact_evaluation
        return fn(ctx.g, state, ply, ctx.cfg.rules)

    def value_full(self, state: GameState, depth: int, ply: int = 0) -> tuple[int, int]:
        ctx = _Ctx(self.graph, SearchConfig(max_depth=depth, alpha_beta=False,
                   use_transposition=False, order_moves=False), None, {})
        return self._ab(ctx, state, depth, ply, -INF, INF, -1)[0], ctx.nodes

    def search(self, state, config=None, ply=0) -> SearchResult:
        cfg = config or SearchConfig()
        start = time.perf_counter()
        ctx = _Ctx(self.graph, cfg, start + cfg.time_limit if cfg.time_limit else None,
                   {}, root_ply=ply)
        root = legal_moves(self.graph, state, cfg.rules, ply)
        if not root:
            return SearchResult(None, self._ev(ctx, state, ply), 0, True,
                                0, 0, 0, time.perf_counter() - start)
        if cfg.order_moves:
            root = self.order_moves(state, root)
        move, score, depth_done, scores, tree = root[0], 0, 0, (), None
        for depth in range(1, max(1, cfg.max_depth) + 1):
            ctx.scores = []
            try:
                _, tree = self._ab(ctx, state, depth, ply, -INF, INF,
                                   cfg.tree_depth if cfg.record_tree else -1)
            except SearchTimeout:
                break
            if not ctx.scores:
                continue
            scores = tuple(ctx.scores)
            best = (max if state.turn is Team.POLICE else min)(scores,
                                                              key=lambda e: e.score)
            move, score, depth_done = best.move, best.score, depth
        return SearchResult(move, score, depth_done, depth_done >= cfg.max_depth,
                            ctx.nodes, ctx.cutoffs, ctx.hits,
                            time.perf_counter() - start, scores, tree)

    def _terminal(self, move: Move, child: GameState, ply: int, rules: RuleSet):
        if move.team is Team.THIEF and move.dst == CENTER:
            return THIEF_WIN_SCORE
        if thief_is_blocked(self.graph, child, rules, ply):
            return POLICE_WIN_SCORE
        return None

    def _ab(self, ctx, state, depth, ply, alpha, beta, record,
            node_move=None, node_depth=None, node_max=None):
        ctx.nodes += 1
        ctx.check()
        cfg = ctx.cfg
        police = state.turn is Team.POLICE
        root = ply == ctx.root_ply
        node = (SearchNode(state, node_move, depth if node_depth is None else node_depth,
                           police if node_max is None else node_max)
                if record >= 0 else None)
        if depth <= 0:
            value = self._ev(ctx, state, ply)
            if node is not None:
                node.score = value
            return value, node

        key = state.position_key() + (min(ply, max(0, cfg.rules.return_cooldown)),)
        if cfg.use_transposition and not root:
            entry = ctx.tt.get(key)
            if entry is not None and entry.depth >= depth:
                ctx.hits += 1
                if entry.flag == EXACT:
                    return entry.score, node
                if entry.flag == LOWER:
                    alpha = max(alpha, entry.score)
                else:
                    beta = min(beta, entry.score)
                if alpha >= beta:
                    return entry.score, node

        moves = legal_moves(ctx.g, state, cfg.rules, ply)
        if not moves:
            value = POLICE_WIN_SCORE if not police else self._ev(ctx, state, ply)
            if node is not None:
                node.score = value
            return value, node
        if cfg.order_moves:
            moves = self.order_moves(state, moves)

        old_alpha, old_beta = alpha, beta
        best = -INF if police else INF
        best_move = None
        for move in moves:
            child = apply_move(ctx.g, state, move, cfg.rules, ply)
            terminal = self._terminal(move, child, ply + 1, cfg.rules)
            if terminal is not None:
                value, child_node = terminal, (
                    SearchNode(child, move, depth - 1, not police, score=terminal)
                    if record >= 1 else None
                )
            else:
                value, child_node = self._ab(ctx, child, depth - 1, ply + 1,
                                             alpha, beta, record - 1,
                                             move, depth - 1, not police)
            if node is not None and child_node is not None:
                node.children.append(child_node)
            if root:
                ctx.scores.append(MoveEvaluation(move, value))
            if police:
                if value > best:
                    best, best_move = value, move
                alpha = max(alpha, best)
            else:
                if value < best:
                    best, best_move = value, move
                beta = min(beta, best)
            if cfg.alpha_beta and not root and alpha >= beta:
                ctx.cutoffs += 1
                if node is not None:
                    node.cutoff = True
                break
        if cfg.use_transposition and not root:
            flag = EXACT if old_alpha < best < old_beta else (
                UPPER if best <= old_alpha else LOWER)
            ctx.tt[key] = _Entry(depth, best, flag, best_move)
        if node is not None:
            node.score, node.alpha, node.beta = int(best), old_alpha, old_beta
        return int(best), node


def choose_move(graph, state, config=None, ply=0) -> SearchResult:
    return SearchEngine(graph).search(state, config, ply)
