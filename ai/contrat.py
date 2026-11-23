"""Contrat minimal des bots : une fonction par camp, aucun moteur partagé."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from core.game_state import GameState, Move
from core.graph import Graph
from core.ruleset import DEFAULT_RULES, RuleSet


@dataclass(frozen=True, slots=True)
class MoveScore:
    score: int
    move: Move


@dataclass(slots=True)
class SearchNode:
    """Nœud réellement visité, exporté pour l'overlay pédagogique."""

    score: int = 0
    maximizing: bool = True
    move: Move | None = None
    children: list["SearchNode"] = field(default_factory=list)
    cutoff: bool = False


@dataclass(slots=True)
class Stats:
    """Compteurs remplis par les bots pour l'affichage pédagogique."""

    nodes: int = 0
    cutoffs: int = 0
    tt_hits: int = 0
    root_scores: tuple[MoveScore, ...] = ()
    tree: SearchNode | None = None


@dataclass(frozen=True, slots=True)
class Context:
    """Informations optionnelles transmises par la partie au bot."""

    rules: RuleSet = DEFAULT_RULES
    depth: int = 3
    repetition_limit: int = 0
    history: tuple[GameState, ...] = ()
    deadline: float | None = None
    stats: Stats | None = None
    collect_tree: bool = False


@dataclass(frozen=True, slots=True)
class Result:
    """Résultat d'une recherche, consommé par l'interface."""

    move: Move
    score: int = 0
    depth: int = 0
    nodes: int = 0
    cutoffs: int = 0
    tt_hits: int = 0
    elapsed: float = 0.0
    completed: bool = True
    root_scores: tuple[MoveScore, ...] = field(default=())
    tree: SearchNode | None = None

Bot = Callable[[Graph, GameState, int, Context | None], Move]

__all__ = ["Bot", "Context", "MoveScore", "Result", "SearchNode", "Stats"]
