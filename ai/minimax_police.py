"""Minimax/alpha-bêta POLICE : camp MAX, évaluation feuille par table exacte."""

from __future__ import annotations

import time

from ai.contrat import Context, MoveScore, SearchNode, Stats
from ai.exact_table import DRAW, ExactTable, table_for
from core.constants import CENTER, Team
from core.game_rules import (
    apply_move,
    police_legal_moves,
    thief_is_blocked,
    thief_legal_moves,
)
from core.game_state import Move
from core.graph import Graph
from core.ruleset import DEFAULT_RULES

INF = 2_000_000

def _leaf(
    graph: Graph,
    state,
    ply: int,
    rules,
    table: ExactTable,
) -> int:
    """Évaluation terminale ou horizon : valeur exacte du point de vue POLICE."""
    return table.value_sid(table.sid_of(state), min(ply, table.cooldown))

def minimax(
    graph: Graph,
    state,
    ply: int,
    depth: int,
    alpha: int,
    beta: int,
    rules,
    table: ExactTable,
    stats: Stats | None,
    deadline: float | None,
    parent: SearchNode | None = None,
    collect: bool = False,
) -> int:
    """MIN/MAX récursif avec élagage alpha-bêta et export optionnel de l'arbre."""
    if stats is not None:
        stats.nodes += 1
    if deadline is not None and time.perf_counter() >= deadline:
        raise TimeoutError

    if depth == 0 or state.thief == CENTER or thief_is_blocked(graph, state, rules, ply):
        return _leaf(graph, state, ply, rules, table)

    if state.turn is Team.POLICE:
        moves = police_legal_moves(graph, state, rules)
        moves.sort(
            key=lambda move: -table.value_sid(
                table.sid_of(apply_move(graph, state, move, rules, ply)),
                min(ply + 1, table.cooldown),
            )
        )
        best = -INF
        for move in moves:
            child = apply_move(graph, state, move, rules, ply)
            node = SearchNode(maximizing=child.turn is Team.POLICE, move=move) if collect else None
            score = minimax(
                graph, child, ply + 1, depth - 1, alpha, beta,
                rules, table, stats, deadline, node, collect,
            )
            if node is not None:
                node.score = score
                if parent is not None:
                    parent.children.append(node)
            best = max(best, score)
            alpha = max(alpha, best)
            if alpha >= beta:
                if stats is not None:
                    stats.cutoffs += 1
                if parent is not None:
                    parent.cutoff = True
                break
        return best

    moves = thief_legal_moves(graph, state, rules, ply)
    field = graph.bfs_distances(CENTER, blocked=set(state.police))
    moves.sort(key=lambda move: field.get(move.dst, 99))
    best = INF
    for move in moves:
        child = apply_move(graph, state, move, rules, ply)
        node = SearchNode(maximizing=child.turn is Team.POLICE, move=move) if collect else None
        score = minimax(
            graph, child, ply + 1, depth - 1, alpha, beta,
            rules, table, stats, deadline, node, collect,
        )
        if node is not None:
            node.score = score
            if parent is not None:
                parent.children.append(node)
        best = min(best, score)
        beta = min(beta, best)
        if alpha >= beta:
            if stats is not None:
                stats.cutoffs += 1
            if parent is not None:
                parent.cutoff = True
            break
    return best

def choose_move(graph: Graph, state, ply: int = 0, ctx: Context | None = None) -> Move:
    """Racine MAX : choisit le coup policier optimal, répétitions incluses."""
    rules = ctx.rules if ctx is not None else DEFAULT_RULES
    moves = police_legal_moves(graph, state, rules)
    if not moves:
        raise ValueError("aucun coup légal pour la police")

    table = table_for(graph, rules)
    depth = max(1, min(ctx.depth if ctx is not None else 3, 4))
    deadline = ctx.deadline if ctx is not None else None
    stats: Stats | None = ctx.stats if ctx is not None else None
    collect = bool(ctx.collect_tree) if ctx is not None else False

    counts: dict[tuple, int] = {}
    if ctx is not None and ctx.repetition_limit > 0:
        for past in ctx.history:
            key = past.position_key()
            counts[key] = counts.get(key, 0) + 1

    best: Move | None = None
    best_key: tuple[int, int, int, str] | None = None
    for depth_index, current_depth in enumerate(range(1, depth + 1)):
        search_deadline = None if depth_index == 0 else deadline
        root = SearchNode(maximizing=state.turn is Team.POLICE) if collect else None
        scored: list[tuple[int, int, int, Move]] = []
        root_scores: list[MoveScore] = []
        try:
            for move in moves:
                child = apply_move(graph, state, move, rules, ply)
                node = SearchNode(maximizing=child.turn is Team.POLICE, move=move) if collect else None
                value = minimax(
                    graph, child, ply + 1, current_depth - 1, -INF, INF,
                    rules, table, stats, search_deadline, node, collect,
                )
                if node is not None:
                    node.score = value
                    if root is not None:
                        root.children.append(node)
                repeats = counts.get(child.position_key(), 0)
                if (
                    counts
                    and value != 0
                    and value < DRAW
                    and repeats + 1 >= ctx.repetition_limit
                ):
                    value = DRAW
                    if node is not None:
                        node.score = value
                reachable = len(graph.bfs_distances(child.thief, blocked=set(child.police)))
                scored.append((value, repeats, reachable, move))
                root_scores.append(MoveScore(value, move))
        except TimeoutError:
            break

        if stats is not None:
            stats.root_scores = tuple(root_scores)
        current = min(scored, key=lambda item: item[:3] + (item[3].dst,))
        if root is not None:
            root.score = current[0]
            stats.tree = root
        if best_key is None or current[:3] + (current[3].dst,) < best_key:
            best_key, best = current[:3] + (current[3].dst,), current[3]
        if current[0] < DRAW:
            break

    assert best is not None
    return best

__all__ = ["choose_move", "minimax"]