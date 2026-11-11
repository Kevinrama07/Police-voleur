"""Tests des contrôleurs de mode : recherche asynchrone, démo, solo, réseau."""

from __future__ import annotations

import time
from typing import Any

import pytest

from ai.minimax import SearchConfig, SearchEngine
from config import GameSettings
from core.constants import GameStatus, Team
from core.game_manager import GameConfig, GameManager
from core.game_rules import legal_moves
from core.game_state import GameState
from core.graph import build_default_graph
from modes.ai_runner import AsyncSearch
from modes.demo import DemoController
from modes.multiplayer import NetworkController
from modes.single_player import SinglePlayerController

GRAPH = build_default_graph()


def game_manager(seed: int = 4) -> GameManager:
    return GameManager(GRAPH, GameConfig(), seed=seed)


class StubNetwork:
    """Transport factice : messages pilotés à la main, envois enregistrés."""

    def __init__(
        self,
        role: Team,
        player_id: str = "P1",
        players: list[dict[str, Any]] | None = None,
    ) -> None:
        self.role = role
        self.player_id = player_id
        self.players = players or [
            {"player_id": "P1", "name": "Joueur 1", "role": role.value},
            {"player_id": "P2", "name": "Joueur 2", "role": "thief" if role is Team.POLICE else "police"},
        ]
        self.started = True
        self.connected = True
        self.game_id = "abcd1234"
        self.peer_left = False
        self.queue: list[dict[str, Any]] = []
        self.sent: list[dict[str, Any]] = []

    def poll(self) -> list[dict[str, Any]]:
        queue, self.queue = self.queue, []
        return queue

    def send(self, kind: str, **payload: Any) -> bool:
        if not self.connected:
            return False
        self.sent.append({"type": kind, **payload})
        return True

    def close(self) -> None:
        self.connected = False


# ---------------------------------------------------------------------- recherche


def test_async_search_returns_a_legal_move() -> None:
    manager = game_manager()
    runner = AsyncSearch()
    try:
        assert runner.start(
            SearchEngine(GRAPH),
            manager.state,
            SearchConfig(max_depth=2, time_limit=2.0),
            manager.ply,
        )
        assert runner.busy
        result = None
        deadline = time.time() + 6.0
        while time.time() < deadline and result is None:
            result = runner.poll()
            time.sleep(0.01)
        assert result is not None
        assert result.move in manager.legal_moves()
        assert result.nodes > 0
    finally:
        runner.shutdown()


def test_async_search_cancel_is_safe() -> None:
    manager = game_manager()
    runner = AsyncSearch()
    try:
        runner.start(SearchEngine(GRAPH), manager.state, SearchConfig(max_depth=3), 0)
        runner.cancel()
        deadline = time.time() + 5.0
        while runner.busy and time.time() < deadline:
            time.sleep(0.01)
        assert runner.poll() is None
    finally:
        runner.shutdown()


# ---------------------------------------------------------------------- démo


def test_demo_plays_without_human() -> None:
    settings = GameSettings(ai_depth=1, ai_time_limit=1.0, demo_speed=4.0, seed=12)
    controller = DemoController(GRAPH, settings)
    try:
        moves = []
        for _ in range(400):
            controller.update(1 / 60)
            move = controller.take_animation()
            if move is not None:
                moves.append(move)
            time.sleep(0.001)
        assert len(moves) >= 2
        assert controller.ply == len(moves)
        teams = [move.team for move in moves]
        assert teams[0] is Team.THIEF
        assert all(left is not right for left, right in zip(teams, teams[1:]))
        assert controller.status is GameStatus.ONGOING
    finally:
        controller.close()


def test_demo_pause_and_step() -> None:
    settings = GameSettings(ai_depth=1, ai_time_limit=1.0, demo_speed=4.0, seed=3)
    controller = DemoController(GRAPH, settings)
    try:
        controller.set_paused(True)
        for _ in range(60):
            controller.update(1 / 60)
        assert controller.ply == 0
        assert controller.take_animation() is None

        controller.step_once()
        deadline = time.time() + 5.0
        while controller.ply == 0 and time.time() < deadline:
            controller.update(1 / 60)
            time.sleep(0.005)
        assert controller.ply == 1
        assert controller.paused
        assert controller.take_animation() is not None

        controller.restart()
        assert controller.ply == 0
        assert not controller.paused
    finally:
        controller.close()


def test_solo_human_thief_moves_first() -> None:
    settings = GameSettings(ai_depth=1, ai_time_limit=1.0, seed=21)
    controller = SinglePlayerController(GRAPH, settings, Team.THIEF)
    try:
        assert controller.can_human_play
        targets = controller.legal_targets()
        assert targets
        vertex = sorted(targets)[0]
        assert controller.handle_board_click(vertex)
        assert controller.ply == 1
        assert controller.take_animation() is not None
        assert not controller.can_human_play
    finally:
        controller.close()


def test_solo_human_police_selects_then_moves() -> None:
    settings = GameSettings(ai_depth=1, ai_time_limit=1.0, seed=8, return_cooldown=0)
    controller = SinglePlayerController(GRAPH, settings, Team.POLICE)
    try:
        assert not controller.can_human_play
        assert controller.legal_targets() == set()
        deadline = time.time() + 6.0
        while not controller.can_human_play and time.time() < deadline:
            controller.update(1 / 60)
            controller.take_animation()
            time.sleep(0.005)
        assert controller.can_human_play
        assert controller.ply == 1

        wing = controller.state.police[0]
        assert not controller.handle_board_click(wing)
        assert controller.selected_police == 0
        targets = controller.legal_targets()
        assert targets
        assert controller.handle_board_click(sorted(targets)[0])
        assert controller.ply == 2
    finally:
        controller.close()


# ---------------------------------------------------------------------- réseau


def _network_start() -> dict[str, Any]:
    manager = game_manager(4)
    return {"state": manager.state.to_dict(), "ply": 0, "seed": 4}


def test_network_controller_keeps_server_seed() -> None:
    controller = NetworkController(
        GRAPH, GameSettings(), StubNetwork(Team.POLICE), _network_start()
    )
    try:
        assert controller.manager.seed == 4
    finally:
        controller.close()


def test_network_controller_applies_server_state() -> None:
    start = _network_start()
    reference = GameManager(GRAPH, GameConfig(), state=GameState.from_dict(start["state"]))
    thief_move = next(
        move for move in legal_moves(GRAPH, reference.state, reference.config.rules, 0)
        if move.team is Team.THIEF
    )
    reference.play(thief_move)

    network = StubNetwork(Team.POLICE)
    controller = NetworkController(GRAPH, GameSettings(), network, start)
    network.queue.append(
        {
            "type": "GAME_STATE",
            "ply": 1,
            "move": thief_move.to_dict(),
            "state": reference.state.to_dict(),
            "status": "ongoing",
        }
    )
    controller.update(0.016)
    assert controller.ply == 1
    assert controller.last_move == thief_move
    assert controller.take_animation() == thief_move
    assert controller.can_human_play


def test_network_controller_sends_police_move() -> None:
    start = _network_start()
    reference = GameManager(GRAPH, GameConfig(), state=GameState.from_dict(start["state"]))
    thief_move = next(
        move for move in legal_moves(GRAPH, reference.state, reference.config.rules, 0)
        if move.team is Team.THIEF
    )
    reference.play(thief_move)

    network = StubNetwork(Team.POLICE)
    controller = NetworkController(GRAPH, GameSettings(), network, start)
    network.queue.append(
        {
            "type": "GAME_STATE",
            "ply": 1,
            "move": thief_move.to_dict(),
            "state": reference.state.to_dict(),
            "status": "ongoing",
        }
    )
    controller.update(0.016)
    assert controller.can_human_play

    wing = controller.state.police[0]
    assert not controller.handle_board_click(wing)
    assert controller.selected_police == 0
    targets = controller.legal_targets()
    assert targets
    assert controller.handle_board_click(sorted(targets)[0])
    assert network.sent and network.sent[-1]["type"] == "MOVE"
    assert network.sent[-1]["ply"] == 1
    assert network.sent[-1]["move"]["team"] == "police"
    assert controller.pending

    network.queue.append({"type": "MOVE_REJECTED", "reason": "Ce mouvement n'est pas autorisé."})
    controller.update(0.016)
    assert not controller.pending
    assert controller.preview is None
    assert "autorisé" in controller.note


def test_network_controller_resyncs_on_gap() -> None:
    start = _network_start()
    network = StubNetwork(Team.POLICE)
    controller = NetworkController(GRAPH, GameSettings(), network, start)
    reference = GameManager(GRAPH, GameConfig(), state=GameState.from_dict(start["state"]))
    for _ in range(3):
        reference.play(reference.legal_moves()[0])

    network.queue.append(
        {
            "type": "GAME_STATE",
            "ply": 3,
            "move": None,
            "state": reference.state.to_dict(),
            "status": "ongoing",
        }
    )
    controller.update(0.016)
    assert controller.ply == 3
    assert controller.state == reference.state
    assert "resynchronisé" in controller.note


def test_network_controller_marks_abandon() -> None:
    network = StubNetwork(Team.THIEF)
    controller = NetworkController(GRAPH, GameSettings(), network, _network_start())
    network.queue.append({"type": "PLAYER_DISCONNECTED", "player_id": "P1"})
    controller.update(0.016)
    assert controller.abandoned
    assert controller.is_over
    assert "déconnecté" in controller.note
    controller.restart()
    assert controller.abandoned


def test_network_opponent_label() -> None:
    network = StubNetwork(Team.POLICE)
    controller = NetworkController(GRAPH, GameSettings(), network, _network_start())
    assert controller.opponent_label() == "Joueur 2 · THIEF"
    assert controller.status in (GameStatus.ONGOING,)
