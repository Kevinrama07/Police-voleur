"""Génération reproductible des configurations initiales."""

from __future__ import annotations

import random

from core.constants import CENTER, POLICE_COUNT, Team
from core.game_state import GameState
from core.graph import Graph


def generate_initial_state(graph: Graph, rng: random.Random | None = None) -> GameState:
    """Voleur au centre ; trois policiers sur des sommets distincts, jamais au centre."""
    generator = rng if rng is not None else random.Random()
    candidates = sorted(vid for vid in graph if vid != CENTER)
    police = tuple(generator.sample(candidates, POLICE_COUNT))
    return GameState(
        thief=graph.center,
        police=(police[0], police[1], police[2]),
        turn=Team.THIEF,
    )


def generate_initial_state_from_seed(graph: Graph, seed: int) -> GameState:
    """Configuration reproductible à partir d'une graine (utile aux tests et au réseau)."""
    return generate_initial_state(graph, random.Random(seed))
