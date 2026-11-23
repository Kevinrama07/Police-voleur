"""Phase 1 : les deux bots sont légaux, déterministes et la police gagne toujours."""

from __future__ import annotations

import random

from ai.contrat import Context, Stats
from ai.minimax_police import choose_move as police_bot
from ai.minimax_police import minimax as police_minimax
from ai.minimax_voleur import choose_move as thief_bot
from ai.minimax_voleur import minimax as thief_minimax
from core.constants import GameStatus, Team
from core.game_manager import GameManager
from core.graph import build_default_graph

GRAPH = build_default_graph()


def _context(manager: GameManager, depth: int = 3) -> Context:
    return Context(
        rules=manager.rules,
        depth=depth,
        repetition_limit=manager.config.repetition_limit,
        history=manager.history,
    )


def _random_thief(manager: GameManager, seed: int):
    rng = random.Random(seed * 1000 + manager.ply)
    moves = [move for move in manager.legal_moves() if move.team is Team.THIEF]
    return rng.choice(moves)


def _alphabeta_thief(manager: GameManager, seed: int):
    return thief_bot(GRAPH, manager.state, manager.ply, _context(manager, depth=3))


def _play(seed: int, thief) -> GameStatus:
    manager = GameManager(GRAPH, seed=seed)
    while not manager.is_over:
        if manager.state.turn is Team.POLICE:
            move = police_bot(GRAPH, manager.state, manager.ply, _context(manager))
        else:
            move = thief(manager, seed)
        assert move in manager.legal_moves()
        manager.play(move)
    return manager.status


def test_les_deux_camps_ont_un_minimax_explicite() -> None:
    assert callable(police_minimax)
    assert callable(thief_minimax)


def test_les_deux_bots_jouent_un_coup_legal() -> None:
    for seed in range(3):
        manager = GameManager(GRAPH, seed=seed)
        bot = police_bot if manager.state.turn is Team.POLICE else thief_bot
        assert bot(GRAPH, manager.state, manager.ply, _context(manager)) in manager.legal_moves()


def test_la_police_bat_un_voleur_aleatoire() -> None:
    for seed in range(5):
        assert _play(seed, _random_thief) is GameStatus.POLICE_WIN


def test_la_police_bat_un_voleur_alphabeta() -> None:
    for seed in range(3):
        assert _play(seed, _alphabeta_thief) is GameStatus.POLICE_WIN


def test_les_bots_sont_deterministes() -> None:
    manager = GameManager(GRAPH, seed=7)
    bot = police_bot if manager.state.turn is Team.POLICE else thief_bot
    ctx = _context(manager)
    assert bot(GRAPH, manager.state, manager.ply, ctx) == bot(
        GRAPH, manager.state, manager.ply, ctx
    )


def test_la_recherche_exporte_un_arbre_visite() -> None:
    manager = GameManager(GRAPH, seed=4)
    stats = Stats()
    ctx = Context(
        rules=manager.rules,
        depth=2,
        repetition_limit=manager.config.repetition_limit,
        history=manager.history,
        stats=stats,
        collect_tree=True,
    )
    bot = police_bot if manager.state.turn is Team.POLICE else thief_bot
    bot(GRAPH, manager.state, manager.ply, ctx)
    assert stats.tree is not None
    assert stats.tree.maximizing is (manager.state.turn is Team.POLICE)
    assert stats.tree.children
    assert any(child.children for child in stats.tree.children)
