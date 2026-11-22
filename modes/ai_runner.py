"""Exécution des bots hors de la boucle graphique (thread dédié)."""

from __future__ import annotations

import time
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import replace

from ai.contrat import Bot, Context, Result, Stats
from core.game_state import GameState
from core.graph import Graph


class AsyncSearch:
    """Lance un bot dans un thread et expose un sondage non bloquant."""

    def __init__(self) -> None:
        self._pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="bot")
        self._future: Future[Result] | None = None

    @property
    def busy(self) -> bool:
        return self._future is not None

    def start(
        self,
        bot: Bot,
        graph: Graph,
        state: GameState,
        ctx: Context,
        ply: int,
    ) -> bool:
        if self._future is not None:
            return False
        if ctx.stats is None:
            ctx = replace(ctx, stats=Stats())
        self._future = self._pool.submit(self._run, bot, graph, state, ctx, ply)
        return True

    @staticmethod
    def _run(bot: Bot, graph: Graph, state: GameState, ctx: Context, ply: int) -> Result:
        started = time.perf_counter()
        assert ctx.stats is not None
        move = bot(graph, state, ply, ctx)
        stats = ctx.stats
        score = next(
            (item.score for item in stats.root_scores if item.move == move),
            0,
        )
        return Result(
            move=move,
            score=score,
            depth=ctx.depth,
            nodes=stats.nodes,
            cutoffs=stats.cutoffs,
            tt_hits=stats.tt_hits,
            elapsed=time.perf_counter() - started,
            completed=True,
            root_scores=stats.root_scores,
            tree=stats.tree,
        )

    def poll(self) -> Result | None:
        """Retourne le résultat dès qu'il est prêt (sinon None), sans bloquer."""
        if self._future is None or not self._future.done():
            return None
        future, self._future = self._future, None
        return future.result()

    def cancel(self) -> None:
        if self._future is not None:
            self._future.cancel()
            self._future = None

    def shutdown(self) -> None:
        self.cancel()
        self._pool.shutdown(wait=False, cancel_futures=True)
