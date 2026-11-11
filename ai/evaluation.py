"""Fonction heuristique d'évaluation, du point de vue de la POLICE (maximizer).

Le voleur est le minimizer : tout score positif favorise la police, tout score
négatif favorise le voleur. Les scores terminaux (±10 000) dominent toujours
l'évaluation heuristique.

Depuis l'amendement des règles (centre contestable + cooldown de retour), la police
peut traverser et occuper le centre : l'évaluation récompense donc la course au
centre (`CENTER_RACE_WEIGHT`) tant qu'il est libre.
"""

from __future__ import annotations

from core.constants import CENTER, POLICE_WIN_SCORE
from core.game_rules import thief_is_blocked, thief_legal_moves
from core.game_state import GameState
from core.graph import Graph
from core.ruleset import DEFAULT_RULES, RuleSet

CENTER_DISTANCE_WEIGHT = 120
POLICE_PROXIMITY_WEIGHT = 40
PATH_PRESSURE_WEIGHT = 35
MOBILITY_WEIGHT = 45
THIEF_PATHS_WEIGHT = 30
REACHABLE_WEIGHT = 3
CENTER_UNREACHABLE_BONUS = 2500
CENTER_RACE_WEIGHT = 60
NO_POLICE_ROUTE_PENALTY = -200
PRESSURE_RADIUS = 2


def _police_distance(
    graph: Graph, state: GameState, police_index: int, target: str
) -> int | None:
    block = state.occupied() - {state.police[police_index], state.thief, target}
    return graph.bfs_distances(state.police[police_index], blocked=block).get(target)


def evaluate(
    graph: Graph,
    state: GameState,
    ply: int | None = None,
    rules: RuleSet = DEFAULT_RULES,
) -> int:
    """Score heuristique (POLICE = maximizer). Les scores terminaux sont prioritaires.

    `ply=None` ignore le cooldown de retour au centre (évaluation « statique ») ;
    la recherche passe la valeur réelle pour rester cohérente avec `legal_moves`.
    """
    if ply is None:
        rules, ply = RuleSet(return_cooldown=0), 0
    if thief_is_blocked(graph, state, rules, ply):
        return POLICE_WIN_SCORE
    if state.thief == CENTER:
        return 0

    police_block = set(state.police)
    distances = graph.bfs_distances(state.thief, blocked=police_block)
    center_distance = distances.get(CENTER)

    score = 0
    if center_distance is None:
        score += CENTER_UNREACHABLE_BONUS
    else:
        score += CENTER_DISTANCE_WEIGHT * center_distance

    legal = thief_legal_moves(graph, state, rules, ply)
    score -= MOBILITY_WEIGHT * len(legal)
    score -= REACHABLE_WEIGHT * len(distances)

    police_distances = [
        distance
        for index in range(len(state.police))
        if (distance := _police_distance(graph, state, index, state.thief)) is not None
    ]
    if police_distances:
        score -= POLICE_PROXIMITY_WEIGHT * min(police_distances)
    else:
        score -= NO_POLICE_ROUTE_PENALTY

    if CENTER not in state.police:
        arrivals = [
            distance
            for index in range(len(state.police))
            if (distance := _police_distance(graph, state, index, CENTER)) is not None
        ]
        if arrivals:
            score -= CENTER_RACE_WEIGHT * min(arrivals)

    if center_distance is not None:
        path = graph.shortest_path(state.thief, CENTER, blocked=police_block)
        if path:
            pressure = 0
            for node in path[1:]:
                for index in range(len(state.police)):
                    distance = _police_distance(graph, state, index, node)
                    if distance is not None and distance <= PRESSURE_RADIUS:
                        pressure += 1
                        break
            score -= PATH_PRESSURE_WEIGHT * pressure

    escape_paths = 0
    for move in legal:
        if CENTER in graph.bfs_distances(move.dst, blocked=police_block):
            escape_paths += 1
    score -= THIEF_PATHS_WEIGHT * escape_paths

    return int(score)
