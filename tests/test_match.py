"""Phase 2 : un seul moteur de match expose les modes AUTO et MANUEL."""

from __future__ import annotations

from config import GameSettings
from core.constants import Team
from core.graph import build_default_graph
from match import MatchController, Mode

GRAPH = build_default_graph()


def test_mode_auto_na_pas_de_camp_humain() -> None:
    controller = MatchController(GRAPH, GameSettings(seed=3), mode=Mode.AUTO)
    try:
        assert controller.human_teams == frozenset()
        assert controller.mode_name == "Automatique"
        assert not controller.can_human_play
        assert controller._is_ai_turn()
    finally:
        controller.close()


def test_mode_manuel_laisse_les_deux_camps_jouer() -> None:
    controller = MatchController(GRAPH, GameSettings(seed=3), mode=Mode.MANUEL)
    try:
        assert controller.human_teams == frozenset(Team)
        assert controller.mode_name == "Manuel"
        assert controller.can_human_play
        assert controller.state.turn is Team.THIEF

        targets = controller.legal_targets()
        assert targets
        assert controller.handle_board_click(sorted(targets)[0])
        assert controller.take_animation() is not None
        assert controller.ply == 1
        assert controller.state.turn is Team.POLICE
        assert controller.can_human_play

        wing = controller.state.police[0]
        assert not controller.handle_board_click(wing)
        assert controller.selected_police == 0
        police_targets = controller.legal_targets()
        assert police_targets
        assert controller.handle_board_click(sorted(police_targets)[0])
        assert controller.ply == 2
    finally:
        controller.close()


def test_un_camp_humain_reste_compatible() -> None:
    controller = MatchController(
        GRAPH, GameSettings(seed=3), human_team=Team.THIEF
    )
    try:
        assert controller.human_teams == frozenset((Team.THIEF,))
        assert controller.mode is Mode.MANUEL
        assert controller.mode_name == "Solo"
    finally:
        controller.close()
