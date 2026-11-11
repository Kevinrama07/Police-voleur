"""Exécution de la recherche IA hors de la boucle graphique (thread dédié)."""

from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor

from ai.minimax import SearchConfig, SearchEngine, SearchResult
from core.game_state import GameState


class AsyncSearch:
    """Lance `SearchEngine.search` dans un thread et expose un sondage non bloquant."""

    def __init__(self) -> None:
        self._pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="minimax")
        self._future: Future[SearchResult] | None = None

    @property
    def busy(self) -> bool:
        return self._future is not None

    def start(
        self,
        engine: SearchEngine,
        state: GameState,
        config: SearchConfig,
        ply: int,
    ) -> bool:
        if self._future is not None:
            return False
        self._future = self._pool.submit(engine.search, state, config, ply)
        return True

    def poll(self) -> SearchResult | None:
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
