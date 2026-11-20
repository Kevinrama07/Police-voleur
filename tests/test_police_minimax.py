from ai.minimax import SearchConfig, SearchEngine
from ai.police_minimax import PoliceMinimaxEngine
from core.constants import GameStatus, Team
from core.game_manager import GameManager
from core.graph import build_default_graph

GRAPH = build_default_graph()


def test_police_minimax_beats_thief_minimax() -> None:
    police = PoliceMinimaxEngine(GRAPH, SearchConfig(max_depth=2, time_limit=1.0))
    thief = SearchEngine(GRAPH)
    thief_config = SearchConfig(max_depth=4, time_limit=1.0)

    for seed in (0, 1, 2):
        manager = GameManager(GRAPH, seed=seed)
        while not manager.is_over:
            if manager.state.turn is Team.POLICE:
                police.set_context(manager.history, manager.config.repetition_limit)
                result = police.search(manager.state, None, manager.ply)
            else:
                result = thief.search(manager.state, thief_config, manager.ply)
            assert result.move is not None
            manager.play(result.move)
        assert manager.status is GameStatus.POLICE_WIN
