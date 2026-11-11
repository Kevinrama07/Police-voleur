"""Tests de l'initialisation des parties."""

from __future__ import annotations

import random

import pytest

from core.constants import CENTER, POLICE_COUNT, Team
from core.game_manager import GameManager
from core.game_state import GameState
from core.graph import build_default_graph
from core.position_generator import (
    generate_initial_state,
    generate_initial_state_from_seed,
)


@pytest.fixture(scope="module")
def graph():
    return build_default_graph()


def test_thief_starts_on_center(graph):
    state = generate_initial_state_from_seed(graph, 1)
    assert state.thief == CENTER
    assert state.turn is Team.THIEF


def test_police_positions_valid(graph):
    for seed in range(200):
        state = generate_initial_state_from_seed(graph, seed)
        assert len(state.police) == POLICE_COUNT
        assert len(set(state.police)) == POLICE_COUNT
        assert CENTER not in state.police
        assert all(position in graph for position in state.police)
        assert state.thief not in state.police


def test_seed_reproducibility(graph):
    first = generate_initial_state_from_seed(graph, 12345)
    second = generate_initial_state_from_seed(graph, 12345)
    assert first == second


def test_different_seeds_vary(graph):
    states = {generate_initial_state_from_seed(graph, seed) for seed in range(50)}
    assert len(states) > 1


def test_generator_accepts_rng(graph):
    state = generate_initial_state(graph, random.Random(7))
    assert state.thief == CENTER
    assert len(set(state.police)) == 3


def test_manager_starts_with_generated_state(graph):
    manager = GameManager(graph, seed=42)
    assert manager.state.thief == CENTER
    assert manager.state.turn is Team.THIEF
    assert manager.status.value == "ongoing"
    assert manager.move_count == 0
    assert len(manager.legal_moves()) == 4


def test_manager_reset_reproduces_state(graph):
    manager = GameManager(graph, seed=99)
    initial = manager.state
    manager.play(manager.legal_moves()[0])
    manager.reset(99)
    assert manager.state == initial
    assert manager.move_count == 0


def test_center_has_four_initial_thief_moves(graph):
    forced = GameState(thief=CENTER, police=("B", "L", "R"), turn=Team.THIEF)
    manager = GameManager(graph, state=forced)
    moves = manager.legal_moves()
    assert {move.dst for move in moves} == {"VCt", "VCb", "HCl", "HCr"}
    assert all(move.team is Team.THIEF for move in moves)


def test_initial_thief_moves_exclude_occupied_neighbors(graph):
    for seed in range(50):
        manager = GameManager(graph, seed=seed)
        occupied = manager.state.occupied()
        for move in manager.legal_moves():
            assert move.dst in graph.neighbors(CENTER)
            assert move.dst not in occupied
