"""Minimax/alpha-bêta VOLEUR : camp MIN, évaluation à 4 termes du point de vue police."""
from __future__ import annotations
import time
from ai.contrat import Context, MoveScore, SearchNode, Stats
from core.constants import CENTER, Team
from core.game_rules import apply_move, legal_moves, thief_is_blocked
from core.game_state import Move
from core.graph import Graph
from core.ruleset import DEFAULT_RULES, RuleSet

MATE = 10_000
INF = 1_000_000

DISTANCE_WEIGHT = 100
MOBILITY_WEIGHT = 40
PROXIMITY_WEIGHT = 30
REACHABLE_WEIGHT = 2
UNREACHABLE_BONUS = 1_500

def evaluate(graph: Graph, state, rules: RuleSet, ply: int) -> int:
    """Heuristique : distance au centre, mobilité, proximité, accessibilité."""
    police = set(state.police)
    distances = graph.bfs_distances(state.thief, blocked=police)
    center_distance = distances.get(CENTER)
    score = (
        UNREACHABLE_BONUS
        if center_distance is None
        else DISTANCE_WEIGHT * center_distance
    )
    score -= MOBILITY_WEIGHT * len(legal_moves(graph, state, rules, ply))
    score -= REACHABLE_WEIGHT * len(distances)
    score -= PROXIMITY_WEIGHT * min(
        graph.bfs_distances(cop, blocked=police - {cop}).get(state.thief, 99)
        for cop in state.police
    )
    return score

def minimax(
    graph: Graph,
    state,
    ply: int,
    depth: int,
    alpha: int,
    beta: int,
    rules: RuleSet,
    deadline: float | None,
    stats: Stats | None,
    parent: SearchNode | None = None,
    collect: bool = False,
) -> int:
    """MIN/MAX récursif avec élagage alpha-bêta et export optionnel de l'arbre."""
    if stats is not None:
        stats.nodes += 1
    if deadline is not None and time.perf_counter() >= deadline:
        raise TimeoutError
    if state.thief == CENTER:
        return -MATE
    if thief_is_blocked(graph, state, rules, ply):
        return MATE
    if depth == 0:
        return evaluate(graph, state, rules, ply)

    moves = legal_moves(graph, state, rules, ply)
    if not moves:
        return 0
    police = set(state.police)
    target = state.thief if state.turn is Team.POLICE else CENTER
    field = graph.bfs_distances(target, blocked=police)
    moves.sort(key=lambda move: field.get(move.dst, 99))

    if state.turn is Team.POLICE:
        best = -INF
        for move in moves:
            child = apply_move(graph, state, move, rules, ply)
            node = SearchNode(maximizing=child.turn is Team.POLICE, move=move) if collect else None
            score = minimax(
                graph, child, ply + 1, depth - 1, alpha, beta,
                rules, deadline, stats, node, collect,
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

    best = INF
    for move in moves:
        if move.dst == CENTER:
            return -MATE
        child = apply_move(graph, state, move, rules, ply)
        node = SearchNode(maximizing=child.turn is Team.POLICE, move=move) if collect else None
        score = minimax(
            graph, child, ply + 1, depth - 1, alpha, beta,
            rules, deadline, stats, node, collect,
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

_value = minimax

def choose_move(graph: Graph, state, ply: int = 0, ctx: Context | None = None) -> Move:
    """Racine MIN : approfondissement itératif, retourne le meilleur coup voleur."""
    rules = ctx.rules if ctx is not None else DEFAULT_RULES
    moves = legal_moves(graph, state, rules, ply)
    if not moves:
        raise ValueError("aucun coup légal pour le voleur")

    depth = max(1, ctx.depth) if ctx is not None else 3
    deadline = ctx.deadline if ctx is not None else None
    stats = ctx.stats if ctx is not None else None
    collect = bool(ctx.collect_tree) if ctx is not None else False
    field = graph.bfs_distances(CENTER, blocked=set(state.police))
    moves.sort(key=lambda move: field.get(move.dst, 99))
    best = moves[0]

    for current_depth in range(1, depth + 1):
        root = SearchNode(maximizing=state.turn is Team.POLICE) if collect else None
        scores: list[MoveScore] = []
        try:
            for move in moves:
                child = apply_move(graph, state, move, rules, ply)
                node = SearchNode(maximizing=child.turn is Team.POLICE, move=move) if collect else None
                score = minimax(
                    graph, child, ply + 1, current_depth - 1,
                    -INF, INF, rules, deadline, stats, node, collect,
                )
                if node is not None:
                    node.score = score
                    if root is not None:
                        root.children.append(node)
                scores.append(MoveScore(score, move))
        except TimeoutError:
            break
        if stats is not None:
            stats.root_scores = tuple(scores)
        chosen = min(scores, key=lambda item: (item.score, item.move.dst))
        best = chosen.move
        if root is not None:
            root.score = chosen.score
            stats.tree = root
        if chosen.score <= -MATE + 1:
            break
    return best

__all__ = ["choose_move", "minimax", "evaluate"]