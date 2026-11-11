"""Benchmark IA : parties complètes IA contre IA, mesures de performance.

Usage : python tools/benchmark_ai.py [--games 20] [--depth 3]
"""

from __future__ import annotations

import argparse
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ai.minimax import SearchConfig, SearchEngine
from core.constants import GameStatus
from core.game_manager import GameManager
from core.graph import build_default_graph


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark IA POLICE – VOLEUR")
    parser.add_argument("--games", type=int, default=20)
    parser.add_argument("--depth", type=int, default=3)
    parser.add_argument("--time-limit", type=float, default=1.0)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()

    graph = build_default_graph()
    engine = SearchEngine(graph)
    config = SearchConfig(max_depth=args.depth, time_limit=args.time_limit)

    outcomes = {status: 0 for status in GameStatus}
    move_times: list[float] = []
    nodes: list[int] = []
    cutoffs: list[int] = []
    moves_per_game: list[int] = []

    for game_index in range(args.games):
        manager = GameManager(graph, seed=args.seed + game_index)
        while not manager.is_over:
            result = engine.search(manager.state, config, ply=manager.ply)
            assert result.move is not None
            move_times.append(result.elapsed)
            nodes.append(result.nodes)
            cutoffs.append(result.cutoffs)
            manager.play(result.move)
        outcomes[manager.status] += 1
        moves_per_game.append(manager.move_count)

    total = args.games
    print(f"parties jouées        : {total}")
    print(f"profondeur            : {args.depth}")
    print(
        "issues                : "
        + ", ".join(f"{status.value}={count}" for status, count in outcomes.items())
    )
    print(f"coups par partie      : moyenne {statistics.mean(moves_per_game):.1f} "
          f"(min {min(moves_per_game)}, max {max(moves_per_game)})")
    print(f"temps par coup        : moyenne {statistics.mean(move_times) * 1000:.2f} ms "
          f"(max {max(move_times) * 1000:.2f} ms)")
    print(f"nœuds par coup        : moyenne {statistics.mean(nodes):.0f} "
          f"(max {max(nodes)})")
    print(f"branches élaguées     : moyenne {statistics.mean(cutoffs):.0f} "
          f"(max {max(cutoffs)})")
    print(f"temps total           : {sum(move_times):.2f} s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
