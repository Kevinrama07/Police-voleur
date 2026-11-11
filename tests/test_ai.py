"""Tests de l'IA : évaluation, Minimax, Alpha-Beta, transposition, temps."""

from __future__ import annotations

import time

import pytest

from ai.evaluation import POLICE_WIN_SCORE, evaluate
from ai.minimax import SearchConfig, SearchEngine, THIEF_WIN_SCORE, choose_move
from core.constants import CENTER, GameStatus, Team
from core.game_manager import GameManager
from core.game_rules import apply_move, legal_moves, outcome_after_move
from core.game_state import GameState, Move
from core.graph import build_default_graph
from core.position_generator import generate_initial_state_from_seed
from core.ruleset import DEFAULT_RULES, RuleSet


@pytest.fixture(scope="module")
def graph():
    return build_default_graph()


@pytest.fixture(scope="module")
def engine(graph):
    return SearchEngine(graph)


def make_state(thief: str, police: tuple[str, str, str], turn: Team) -> GameState:
    return GameState(thief=thief, police=police, turn=turn)


def test_ai_returns_legal_move_for_both_teams(graph, engine):
    for seed in range(10):
        state = generate_initial_state_from_seed(graph, seed)
        result = engine.search(state, SearchConfig(max_depth=3))
        assert result.move is not None
        assert result.move in legal_moves(graph, state)
        manager = GameManager(graph, seed=seed, state=state)
        status = manager.play(result.move)
        assert status in (GameStatus.ONGOING, GameStatus.POLICE_WIN, GameStatus.THIEF_WIN)
        follow_up = manager.state
        if not manager.is_over:
            result = engine.search(follow_up, SearchConfig(max_depth=3))
            assert result.move in legal_moves(graph, follow_up)


def test_alpha_beta_matches_minimax_exactly(graph, engine):
    configs = [
        SearchConfig(max_depth=4, alpha_beta=True, use_transposition=False, order_moves=False),
        SearchConfig(max_depth=4, alpha_beta=False, use_transposition=False, order_moves=False),
    ]
    states = [
        generate_initial_state_from_seed(graph, seed) for seed in (0, 3, 7)
    ]
    states.append(make_state("HCl", ("EA2", "EA7", "B"), Team.THIEF))
    states.append(make_state("EA2", ("T", "J1", "L"), Team.POLICE))
    for state in states:
        pruned = engine.search(state, configs[0])
        full = engine.search(state, configs[1])
        assert pruned.score == full.score, (state, pruned.score, full.score)
        assert pruned.move == full.move


def test_alpha_beta_prunes_nodes(graph, engine):
    state = generate_initial_state_from_seed(graph, 3)
    pruned = engine.search(
        state,
        SearchConfig(max_depth=5, alpha_beta=True, use_transposition=False, order_moves=False),
    )
    full = engine.search(
        state,
        SearchConfig(max_depth=5, alpha_beta=False, use_transposition=False, order_moves=False),
    )
    assert pruned.cutoffs > 0
    assert pruned.nodes < full.nodes


def test_transposition_table_preserves_result(graph, engine):
    state = generate_initial_state_from_seed(graph, 5)
    with_tt = engine.search(
        state, SearchConfig(max_depth=4, use_transposition=True)
    )
    without_tt = engine.search(
        state, SearchConfig(max_depth=4, use_transposition=False)
    )
    assert with_tt.score == without_tt.score
    assert with_tt.move == without_tt.move


def test_iterative_deepening_reaches_depth(graph, engine):
    state = generate_initial_state_from_seed(graph, 1)
    result = engine.search(state, SearchConfig(max_depth=4))
    assert result.completed
    assert result.depth == 4
    assert len(result.root_scores) == len(legal_moves(graph, state))
    assert result.score == max(item.score for item in result.root_scores)


def test_time_limit_is_respected(graph, engine):
    state = generate_initial_state_from_seed(graph, 2)
    started = time.perf_counter()
    result = engine.search(
        state, SearchConfig(max_depth=40, time_limit=0.05)
    )
    elapsed = time.perf_counter() - started
    assert elapsed < 2.0
    assert result.move is not None
    assert result.move in legal_moves(graph, state)
    assert result.depth < 40


def test_thief_scores_center_return(graph, engine):
    state = make_state("HCl", ("EA2", "EA7", "B"), Team.THIEF)
    result = engine.search(
        state, SearchConfig(max_depth=2, rules=RuleSet(return_cooldown=0))
    )
    assert result.score == THIEF_WIN_SCORE
    assert result.move is not None and result.move.dst == CENTER


def test_thief_respects_center_cooldown(graph, engine):
    state = make_state("HCl", ("EA2", "EA7", "B"), Team.THIEF)
    early = engine.search(state, SearchConfig(max_depth=2))
    assert early.move is not None and early.move.dst != CENTER
    assert early.score != THIEF_WIN_SCORE
    late = engine.search(state, SearchConfig(max_depth=2), ply=DEFAULT_RULES.return_cooldown)
    assert late.score == THIEF_WIN_SCORE
    assert late.move is not None and late.move.dst == CENTER


def test_police_blocks_center_before_cooldown_expires(graph, engine):
    state = make_state("HCl", ("VCb", "EA6", "L"), Team.POLICE)
    ply = DEFAULT_RULES.return_cooldown - 1
    result = engine.search(state, SearchConfig(max_depth=2), ply=ply)
    assert result.move is not None and result.move.dst == CENTER


def test_police_finds_blocking_move(graph, engine):
    assert set(graph.neighbors("EA2")) == {"T", "EALt", "J1"}
    state = make_state("EA2", ("T", "J1", "L"), Team.POLICE)
    result = engine.search(state, SearchConfig(max_depth=3))
    assert result.score == POLICE_WIN_SCORE
    assert result.move == Move(Team.POLICE, "L", "EALt", police_index=2)
    blocked = apply_move(graph, state, result.move)
    assert outcome_after_move(graph, state, result.move, blocked) is GameStatus.POLICE_WIN


def test_evaluation_terminal_states(graph):
    blocked = make_state("EA2", ("T", "J1", "EALt"), Team.THIEF)
    assert evaluate(graph, blocked) == POLICE_WIN_SCORE
    assert evaluate(graph, make_state(CENTER, ("EA2", "EA7", "B"), Team.THIEF)) == 0


def test_evaluation_rewards_police_proximity(graph):
    thief = "B"
    near = make_state(thief, ("EA6", "EA7", "J2"), Team.POLICE)
    far = make_state(thief, ("T", "EA1", "EA2"), Team.POLICE)
    assert evaluate(graph, near) > evaluate(graph, far)


def test_evaluation_rewards_distance_from_center(graph):
    police = ("EA7", "B", "EA6")
    close = make_state("HAL", police, Team.POLICE)
    distant = make_state("EA2", police, Team.POLICE)
    assert evaluate(graph, close) < evaluate(graph, distant)


def test_evaluation_rewards_reduced_mobility(graph):
    thief = "EA2"
    two_blocked = make_state(thief, ("J1", "EA1", "J2"), Team.POLICE)
    free = make_state(thief, ("B", "EA6", "J2"), Team.POLICE)
    assert evaluate(graph, two_blocked) > evaluate(graph, free)


def test_recorded_tree_matches_real_search(graph, engine):
    state = generate_initial_state_from_seed(graph, 4)
    result = engine.search(
        state, SearchConfig(max_depth=3, record_tree=True, tree_depth=2)
    )
    assert result.tree is not None
    root_moves = legal_moves(graph, state)
    assert {child.move for child in result.tree.children} <= set(root_moves)
    assert len(result.tree.children) == len(root_moves)
    scores = [child.score for child in result.tree.children]
    expected = max(scores) if result.tree.maximizing else min(scores)
    assert result.tree.score == expected
    for child in result.tree.children:
        assert child.state == apply_move(graph, state, child.move)


def test_choose_move_helper(graph):
    state = generate_initial_state_from_seed(graph, 6)
    result = choose_move(graph, state, SearchConfig(max_depth=2))
    assert result.move in legal_moves(graph, state)
