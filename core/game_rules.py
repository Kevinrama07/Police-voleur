"""Règles officielles : génération des coups légaux, application, conditions de victoire.

Deux ajustements documentés (validés par l'utilisateur) rendent la partie réellement
disputée — sans eux, le voleur gagne toujours en 3 demi-coups :

- `RuleSet.return_cooldown` : le retour au centre est illégal pendant les premiers
  demi-coups (défaut 10) ;
- `RuleSet.center_contestable` : les policiers peuvent occuper le centre une fois que
  le voleur l'a quitté (défaut activé).
"""

from __future__ import annotations

from typing import Iterable

from core.constants import CENTER, GameStatus, Team
from core.game_state import GameState, Move
from core.graph import Graph
from core.ruleset import DEFAULT_RULES, RuleSet


class IllegalMoveError(ValueError):
    """Coup refusé par les règles."""


class GameOverError(RuntimeError):
    """Tentative de jouer sur une partie terminée."""


def thief_legal_moves(
    graph: Graph,
    state: GameState,
    rules: RuleSet = DEFAULT_RULES,
    ply: int = 0,
) -> list[Move]:
    """Coups légaux du voleur selon l'occupation courante (indépendant du tour)."""
    occupied = state.occupied()
    can_return = rules.thief_can_return(ply)
    return [
        Move(Team.THIEF, state.thief, neighbor)
        for neighbor in graph.neighbors(state.thief)
        if neighbor not in occupied and (can_return or neighbor != CENTER)
    ]


def thief_is_blocked(
    graph: Graph,
    state: GameState,
    rules: RuleSet = DEFAULT_RULES,
    ply: int = 0,
) -> bool:
    """Vrai si le voleur n'a plus aucun déplacement légal."""
    return not thief_legal_moves(graph, state, rules, ply)


def police_legal_moves(
    graph: Graph,
    state: GameState,
    rules: RuleSet = DEFAULT_RULES,
) -> list[Move]:
    """Coups légaux des policiers : un seul policier, jamais sur un sommet occupé."""
    occupied = state.occupied()
    moves: list[Move] = []
    for index, position in enumerate(state.police):
        for neighbor in graph.neighbors(position):
            if neighbor in occupied:
                continue
            if neighbor == CENTER and not rules.center_contestable:
                continue
            moves.append(Move(Team.POLICE, position, neighbor, police_index=index))
    return moves


def legal_moves(
    graph: Graph,
    state: GameState,
    rules: RuleSet = DEFAULT_RULES,
    ply: int = 0,
) -> list[Move]:
    """Tous les coups légaux pour l'équipe dont c'est le tour."""
    if state.turn is Team.THIEF:
        return thief_legal_moves(graph, state, rules, ply)
    return police_legal_moves(graph, state, rules)


def is_legal_move(
    graph: Graph,
    state: GameState,
    move: Move,
    rules: RuleSet = DEFAULT_RULES,
    ply: int = 0,
) -> bool:
    return move in legal_moves(graph, state, rules, ply)


def apply_move(
    graph: Graph,
    state: GameState,
    move: Move,
    rules: RuleSet = DEFAULT_RULES,
    ply: int = 0,
) -> GameState:
    """Valide puis applique un coup ; retourne le nouvel état avec le tour suivant."""
    if move.team is not state.turn:
        raise IllegalMoveError(
            f"coup de {move.team.value} pendant le tour de {state.turn.value}"
        )
    if not is_legal_move(graph, state, move, rules, ply):
        raise IllegalMoveError(f"coup illégal {move.src}->{move.dst}")
    if move.team is Team.THIEF:
        return GameState(
            thief=move.dst,
            police=state.police,
            turn=Team.POLICE,
        )
    assert move.police_index is not None
    police = list(state.police)
    police[move.police_index] = move.dst
    return GameState(
        thief=state.thief,
        police=(police[0], police[1], police[2]),
        turn=Team.THIEF,
    )


def outcome_after_move(
    graph: Graph,
    previous: GameState,
    move: Move,
    state: GameState,
    rules: RuleSet = DEFAULT_RULES,
    ply: int = 0,
) -> GameStatus:
    """Statut résultant d'un coup appliqué ; priorité au retour du voleur au centre.

    `ply` est le nombre de demi-coups déjà joués *après* ce coup : il conditionne
    la légalité du retour au centre et donc la détection du blocage.
    """
    if move.team is Team.THIEF and move.dst == CENTER:
        return GameStatus.THIEF_WIN
    if thief_is_blocked(graph, state, rules, ply):
        return GameStatus.POLICE_WIN
    return GameStatus.ONGOING


def effective_moves(moves: Iterable[Move]) -> list[Move]:
    """Filtre de sécurité : ne conserve que des coups non triviaux (src != dst)."""
    return [move for move in moves if move.src != move.dst]
