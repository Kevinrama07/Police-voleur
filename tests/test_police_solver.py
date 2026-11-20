"""Tests du solveur exact de la POLICE : victoire forcée quel que soit le voleur."""

from __future__ import annotations

import itertools

import pytest

from ai.minimax import SearchConfig, SearchEngine
from ai.police_solver import PoliceSolverEngine, solved_game, _DRAW_VALUE
from core.constants import CENTER, GameStatus, Team
from core.game_manager import GameConfig, GameManager
from core.game_rules import apply_move, thief_legal_moves
from core.game_state import GameState
from core.graph import build_default_graph
from core.position_generator import generate_initial_state_from_seed
from core.ruleset import DEFAULT_RULES, RuleSet

GRAPH = build_default_graph()
CONFIG = SearchConfig(rules=DEFAULT_RULES)


@pytest.fixture(scope="module")
def solver():
    return solved_game(GRAPH, DEFAULT_RULES)


def _history_counts(manager: GameManager) -> dict[tuple, int]:
    counts: dict[tuple, int] = {}
    for state in manager.history:
        key = state.position_key()
        counts[key] = counts.get(key, 0) + 1
    return counts


def _police_engine() -> PoliceSolverEngine:
    return PoliceSolverEngine(GRAPH)


def _police_move(engine: PoliceSolverEngine, manager: GameManager):
    engine.set_context(manager.history, 3)
    result = engine.search(manager.state, CONFIG, manager.ply)
    return result.move


def _optimal_thief(solver, manager: GameManager):
    """Voleur le plus fort possible : connaît la table et cherche aussi les répétitions."""
    state = manager.state
    ply = manager.ply
    counts = _history_counts(manager)
    best_key = None
    best_move = None
    for move in thief_legal_moves(GRAPH, state, DEFAULT_RULES, ply):
        if move.dst == CENTER:
            return move
        child = apply_move(GRAPH, state, move, DEFAULT_RULES, ply)
        key = (solver.value(child, ply + 1), counts.get(child.position_key(), 0))
        if best_key is None or key > best_key:
            best_key, best_move = key, move
    return best_move


def _repetition_hunter(solver, manager: GameManager):
    """Voleur qui privilégie délibérément une nulle par triple répétition."""
    state = manager.state
    ply = manager.ply
    counts = _history_counts(manager)
    best_key = None
    best_move = None
    for move in thief_legal_moves(GRAPH, state, DEFAULT_RULES, ply):
        if move.dst == CENTER:
            return move
        child = apply_move(GRAPH, state, move, DEFAULT_RULES, ply)
        key = (counts.get(child.position_key(), 0), solver.value(child, ply + 1))
        if best_key is None or key > best_key:
            best_key, best_move = key, move
    return best_move


def _random_thief(manager: GameManager):
    moves = thief_legal_moves(GRAPH, manager.state, DEFAULT_RULES, manager.ply)
    return moves[0] if moves else None


def _minimax_thief(engine: SearchEngine, manager: GameManager):
    result = engine.search(
        manager.state,
        SearchConfig(max_depth=2, time_limit=1.0, rules=DEFAULT_RULES),
        manager.ply,
    )
    return result.move


def _play(seed: int, thief) -> GameStatus:
    engine = _police_engine()
    manager = GameManager(GRAPH, config=GameConfig(rules=DEFAULT_RULES), seed=seed)
    while not manager.is_over:
        move = (
            _police_move(engine, manager)
            if manager.state.turn is Team.POLICE
            else thief(manager)
        )
        assert move is not None
        manager.play(move)
    return manager.status


def test_every_initial_position_is_a_forced_win(solver):
    others = [vertex for vertex in GRAPH if vertex != CENTER]
    non_winning = []
    for police in itertools.combinations(others, 3):
        state = GameState(thief=CENTER, police=police, turn=Team.THIEF)
        if solver.value(state, 0) >= _DRAW_VALUE:
            non_winning.append(police)
    assert non_winning == []
    assert solver.lose_states + solver.win_states == solver.valid_count
    assert solver.win_states > 0


def test_solver_returns_legal_move_and_decreases_distance(solver):
    for seed in range(12):
        manager = GameManager(GRAPH, config=GameConfig(rules=DEFAULT_RULES), seed=seed)
        thief_move = thief_legal_moves(
            GRAPH, manager.state, DEFAULT_RULES, manager.ply
        )[0]
        manager.play(thief_move)
        assert manager.state.turn is Team.POLICE
        move = _police_move(_police_engine(), manager)
        assert move is not None
        assert move in manager.legal_moves()
        before = solver.value(manager.state, manager.ply)
        after_state = apply_move(GRAPH, manager.state, move, DEFAULT_RULES, manager.ply)
        after = solver.value(after_state, manager.ply + 1)
        assert solver.is_win(before)
        assert solver.is_win(after)
        assert after <= before


def test_police_always_wins_against_optimal_adversary(solver):
    for seed in range(8):
        status = _play(seed, lambda manager: _optimal_thief(solver, manager))
        assert status is GameStatus.POLICE_WIN


def test_police_always_wins_against_repetition_hunter(solver):
    for seed in range(20):
        status = _play(
            seed, lambda manager: _repetition_hunter(solver, manager)
        )
        assert status is GameStatus.POLICE_WIN


def test_police_always_wins_against_minimax_thief():
    thief_engine = SearchEngine(GRAPH)
    for seed in range(4):
        status = _play(
            seed, lambda manager: _minimax_thief(thief_engine, manager)
        )
        assert status is GameStatus.POLICE_WIN


def test_police_always_wins_against_random_thief():
    for seed in range(8):
        status = _play(seed, _random_thief)
        assert status is GameStatus.POLICE_WIN


def test_engine_exposes_search_result_for_interface(solver):
    manager = GameManager(GRAPH, config=GameConfig(rules=DEFAULT_RULES), seed=3)
    manager.play(thief_legal_moves(GRAPH, manager.state, DEFAULT_RULES, 0)[0])
    result = _police_engine().search(manager.state, CONFIG, manager.ply)
    assert result.move in manager.legal_moves()
    assert result.completed
    assert result.depth > 0
    assert result.score > 0
    assert result.root_scores
    assert result.nodes == solver.node_count


def test_engine_refuses_thief_turns():
    manager = GameManager(GRAPH, config=GameConfig(rules=DEFAULT_RULES), seed=3)
    with pytest.raises(ValueError):
        _police_engine().search(manager.state, CONFIG, manager.ply)


def test_solver_still_returns_legal_moves_when_center_is_not_contestable():
    rules = RuleSet(return_cooldown=10, center_contestable=False)
    solver = solved_game(GRAPH, rules)
    manager = GameManager(GRAPH, config=GameConfig(rules=rules), seed=5)
    manager.play(thief_legal_moves(GRAPH, manager.state, rules, 0)[0])
    move, value, entries = solver.best_move(manager.state, manager.ply)
    assert move is not None
    assert move in manager.legal_moves()
    assert entries
