"""Tests des règles officielles : coups légaux, alternance, victoires, nuls."""

from __future__ import annotations

import random

import pytest

from core.constants import CENTER, GameStatus, Team
from core.game_manager import GameConfig, GameManager
from core.game_rules import (
    GameOverError,
    IllegalMoveError,
    apply_move,
    is_legal_move,
    legal_moves,
    thief_is_blocked,
    thief_legal_moves,
)
from core.game_state import GameState, Move
from core.graph import build_default_graph
from core.ruleset import DEFAULT_RULES, RuleSet


@pytest.fixture(scope="module")
def graph():
    return build_default_graph()


def state(thief, police, turn):
    return GameState(thief=thief, police=tuple(police), turn=turn)


def test_thief_moves_from_center_are_adjacent(graph):
    current = state(CENTER, ("B", "L", "R"), Team.THIEF)
    moves = legal_moves(graph, current)
    assert {move.dst for move in moves} == set(graph.neighbors(CENTER))
    assert all(graph.is_adjacent(move.src, move.dst) for move in moves)


def test_thief_cannot_move_onto_occupied(graph):
    current = state("T", ("J1", "L", "R"), Team.THIEF)
    moves = thief_legal_moves(graph, current)
    assert "J1" not in {move.dst for move in moves}
    assert {move.dst for move in moves} == {"EA2", "EA1"}


def test_thief_blocked_detection(graph):
    current = state("EALt", ("EA2", "L", "HAL"), Team.THIEF)
    assert thief_is_blocked(graph, current)
    assert thief_legal_moves(graph, current) == []


def test_manager_declares_police_win_on_blocked_initial_state(graph):
    manager = GameManager(graph, state=state("EALt", ("EA2", "L", "HAL"), Team.THIEF))
    assert manager.status is GameStatus.POLICE_WIN
    assert manager.legal_moves() == []


def test_police_may_enter_center_after_thief_leaves(graph):
    current = state("T", ("HCl", "B", "R"), Team.POLICE)
    moves = legal_moves(graph, current)
    assert CENTER in {move.dst for move in moves}
    assert any(move.dst == "HAL" for move in moves)


def test_center_can_be_reserved_for_thief(graph):
    strict = RuleSet(center_contestable=False)
    current = state("T", ("HCl", "B", "R"), Team.POLICE)
    moves = legal_moves(graph, current, strict)
    assert CENTER not in {move.dst for move in moves}


def test_thief_center_return_needs_cooldown(graph):
    current = state("VCt", ("B", "L", "R"), Team.THIEF)
    for ply in range(DEFAULT_RULES.return_cooldown):
        assert CENTER not in {move.dst for move in legal_moves(graph, current, ply=ply)}
    later = {move.dst for move in legal_moves(graph, current, ply=DEFAULT_RULES.return_cooldown)}
    assert CENTER in later
    assert CENTER in {move.dst for move in legal_moves(graph, current, RuleSet(return_cooldown=0))}


def test_manager_enforces_cooldown_then_allows_win(graph):
    cycle = [
        Move(Team.THIEF, "VCt", "J1"),
        Move(Team.POLICE, "B", "EA7", police_index=0),
        Move(Team.THIEF, "J1", "VCt"),
        Move(Team.POLICE, "EA7", "B", police_index=0),
    ]
    forced = state("VCt", ("B", "EA6", "L"), Team.THIEF)

    strict = GameManager(
        graph,
        config=GameConfig(repetition_limit=0, max_moves=0),
        state=forced,
    )
    while strict.ply < 8:
        strict.play(cycle[strict.ply % 4])
    assert strict.ply == 8
    assert strict.state.turn is Team.THIEF
    assert strict.state.thief == "VCt"
    with pytest.raises(IllegalMoveError):
        strict.play(Move(Team.THIEF, "VCt", CENTER))

    relaxed = GameManager(
        graph,
        config=GameConfig(repetition_limit=0, max_moves=0, rules=RuleSet(return_cooldown=8)),
        state=forced,
    )
    while relaxed.ply < 8:
        relaxed.play(cycle[relaxed.ply % 4])
    assert relaxed.ply == 8
    assert relaxed.state.turn is Team.THIEF
    assert relaxed.state.thief == "VCt"
    assert relaxed.play(Move(Team.THIEF, "VCt", CENTER)) is GameStatus.THIEF_WIN


def test_only_one_police_moves_per_turn(graph):
    current = state("T", ("EA2", "L", "R"), Team.POLICE)
    for move in legal_moves(graph, current):
        assert move.police_index in (0, 1, 2)
        after = apply_move(graph, current, move)
        changed = [
            index
            for index in range(3)
            if current.police[index] != after.police[index]
        ]
        assert changed == [move.police_index]
        assert after.thief == current.thief


def test_turn_alternation(graph):
    current = state(CENTER, ("B", "L", "R"), Team.THIEF)
    thief_move = legal_moves(graph, current)[0]
    after_thief = apply_move(graph, current, thief_move)
    assert after_thief.turn is Team.POLICE
    police_move = legal_moves(graph, after_thief)[0]
    after_police = apply_move(graph, after_thief, police_move)
    assert after_police.turn is Team.THIEF


def test_wrong_team_move_rejected(graph):
    current = state(CENTER, ("B", "L", "R"), Team.THIEF)
    with pytest.raises(IllegalMoveError):
        apply_move(graph, current, Move(Team.POLICE, "B", "EA6", police_index=0))


def test_non_adjacent_move_rejected(graph):
    current = state(CENTER, ("B", "L", "R"), Team.THIEF)
    with pytest.raises(IllegalMoveError):
        apply_move(graph, current, Move(Team.THIEF, CENTER, "B"))


def test_occupied_destination_rejected(graph):
    current = state(CENTER, ("VCt", "L", "R"), Team.THIEF)
    assert not is_legal_move(graph, current, Move(Team.THIEF, CENTER, "VCt"))
    with pytest.raises(IllegalMoveError):
        apply_move(graph, current, Move(Team.THIEF, CENTER, "VCt"))


def test_police_move_from_wrong_source_rejected(graph):
    current = state("T", ("EA2", "L", "R"), Team.POLICE)
    with pytest.raises(IllegalMoveError):
        apply_move(graph, current, Move(Team.POLICE, "B", "EA6", police_index=0))


def test_thief_wins_by_returning_to_center(graph):
    manager = GameManager(
        graph,
        config=GameConfig(rules=RuleSet(return_cooldown=0)),
        state=state("VCt", ("B", "L", "R"), Team.THIEF),
    )
    status = manager.play(Move(Team.THIEF, "VCt", CENTER))
    assert status is GameStatus.THIEF_WIN
    assert manager.is_over
    assert manager.state.thief == CENTER


def test_thief_win_has_priority_over_blocking(graph):
    manager = GameManager(
        graph,
        config=GameConfig(rules=RuleSet(return_cooldown=0)),
        state=state("VCt", ("J1", "HCl", "HCr"), Team.THIEF),
    )
    status = manager.play(Move(Team.THIEF, "VCt", CENTER))
    assert status is GameStatus.THIEF_WIN


def test_police_win_by_completing_block(graph):
    manager = GameManager(graph, state=state("EALt", ("EA2", "L", "HCl"), Team.POLICE))
    status = manager.play(Move(Team.POLICE, "HCl", "HAL", police_index=2))
    assert status is GameStatus.POLICE_WIN
    assert thief_is_blocked(graph, manager.state)


def test_play_after_game_over_raises(graph):
    manager = GameManager(
        graph,
        config=GameConfig(rules=RuleSet(return_cooldown=0)),
        state=state("VCt", ("B", "L", "R"), Team.THIEF),
    )
    manager.play(Move(Team.THIEF, "VCt", CENTER))
    with pytest.raises(GameOverError):
        manager.play(Move(Team.THIEF, "VCt", CENTER))


def test_repetition_draw(graph):
    manager = GameManager(
        graph,
        config=GameConfig(repetition_limit=2, max_moves=0),
        state=state("T", ("B", "L", "R"), Team.THIEF),
    )
    manager.play(Move(Team.THIEF, "T", "EA2"))
    manager.play(Move(Team.POLICE, "B", "EA7", police_index=0))
    manager.play(Move(Team.THIEF, "EA2", "T"))
    status = manager.play(Move(Team.POLICE, "EA7", "B", police_index=0))
    assert status is GameStatus.DRAW
    assert manager.status is GameStatus.DRAW


def test_repetition_disabled(graph):
    manager = GameManager(
        graph,
        config=GameConfig(repetition_limit=0, max_moves=0),
        state=state("T", ("B", "L", "R"), Team.THIEF),
    )
    moves = [
        Move(Team.THIEF, "T", "EA2"),
        Move(Team.POLICE, "B", "EA7", police_index=0),
        Move(Team.THIEF, "EA2", "T"),
        Move(Team.POLICE, "EA7", "B", police_index=0),
    ]
    for move in moves:
        assert manager.play(move) is GameStatus.ONGOING
    assert manager.status is GameStatus.ONGOING


def test_max_moves_draw_is_not_a_victory(graph):
    manager = GameManager(
        graph,
        config=GameConfig(repetition_limit=0, max_moves=2),
        state=state("T", ("B", "L", "R"), Team.THIEF),
    )
    assert manager.play(Move(Team.THIEF, "T", "EA2")) is GameStatus.ONGOING
    status = manager.play(Move(Team.POLICE, "B", "EA7", police_index=0))
    assert status is GameStatus.DRAW
    assert status not in (GameStatus.POLICE_WIN, GameStatus.THIEF_WIN)


def test_state_rejects_duplicate_police():
    with pytest.raises(ValueError):
        GameState(thief="T", police=("B", "B", "R"), turn=Team.THIEF)


def test_state_rejects_thief_on_police_vertex():
    with pytest.raises(ValueError):
        GameState(thief="B", police=("B", "L", "R"), turn=Team.THIEF)


def test_move_validation():
    with pytest.raises(ValueError):
        Move(Team.POLICE, "B", "EA6")
    with pytest.raises(ValueError):
        Move(Team.POLICE, "B", "EA6", police_index=3)
    with pytest.raises(ValueError):
        Move(Team.THIEF, "B", "EA6", police_index=0)


def test_random_playouts_preserve_invariants(graph):
    rng = random.Random(2024)
    for seed in range(30):
        manager = GameManager(graph, config=GameConfig(max_moves=300), seed=seed)
        while not manager.is_over:
            moves = manager.legal_moves()
            assert moves, "partie en cours sans coup légal"
            for move in moves:
                assert move.team is manager.state.turn
                assert graph.is_adjacent(move.src, move.dst)
                assert move.dst not in manager.state.occupied()
                if move.team is Team.POLICE and move.dst == CENTER:
                    assert manager.state.thief != CENTER
            state_before = manager.state
            move = rng.choice(moves)
            manager.play(move)
            state_after = manager.state
            assert state_after.turn is state_before.turn.opponent
            occupied = state_after.occupied()
            assert len(occupied) == 4
            if manager.status is GameStatus.THIEF_WIN:
                assert move.team is Team.THIEF and move.dst == CENTER
            if manager.status is GameStatus.POLICE_WIN:
                assert thief_is_blocked(graph, manager.state)
        assert manager.status in (
            GameStatus.POLICE_WIN,
            GameStatus.THIEF_WIN,
            GameStatus.DRAW,
        )
