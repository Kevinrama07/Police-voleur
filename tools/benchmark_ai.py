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

from ai.contrat import Context, Stats
from ai.minimax_police import choose_move as police_bot
from ai.minimax_voleur import choose_move as thief_bot
from core.constants import Team
from core.constants import GameStatus
from core.game_manager import GameManager
from core.graph import build_default_graph
from core.ruleset import DEFAULT_RULES


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark IA POLICE – VOLEUR")
    parser.add_argument("--games", type=int, default=20)
    parser.add_argument("--depth", type=int, default=3)
    parser.add_argument("--time-limit", type=float, default=1.0)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()

    graph = build_default_graph()
    outcomes = {status: 0 for status in GameStatus}
    move_times: list[float] = []
    nodes: list[int] = []
    cutoffs: list[int] = []
    moves_per_game: list[int] = []

    for game_index in range(args.games):
        manager = GameManager(graph, seed=args.seed + game_index)
        while not manager.is_over:
            stats = Stats()
            deadline = None
            if args.time_limit > 0:
                deadline = time.perf_counter() + args.time_limit
            ctx = Context(
                rules=DEFAULT_RULES,
                depth=max(1, args.depth),
                repetition_limit=manager.config.repetition_limit,
                history=manager.history,
                deadline=deadline,
                stats=stats,
            )
            bot = police_bot if manager.state.turn is Team.POLICE else thief_bot
            started = time.perf_counter()
            move = bot(graph, manager.state, manager.ply, ctx)
            move_times.append(time.perf_counter() - started)
            nodes.append(stats.nodes)
            cutoffs.append(stats.cutoffs)
            manager.play(move)
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
