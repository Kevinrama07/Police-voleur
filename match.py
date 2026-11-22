"""Moteur de match unique : modes AUTO et MANUEL, IA asynchrone et animations."""

from __future__ import annotations

import random
import time
from enum import Enum

from ai.contrat import Bot, Context, Result, Stats
from ai.minimax_police import choose_move as police_bot
from ai.minimax_voleur import choose_move as thief_bot
from config import DEMO_STEP_DELAY_SECONDS, GameSettings
from core.constants import GameStatus, Team
from core.game_manager import GameManager
from core.game_state import GameState, Move
from core.graph import Graph
from modes.ai_runner import AsyncSearch
from stats import StatsStore

PREVIEW_SECONDS = 0.34


class Mode(str, Enum):
    """Deux façons de jouer : bots partout, ou deux humains sur le même écran."""

    AUTO = "auto"
    MANUEL = "manuel"


class MatchController:
    """Pilote une partie : tours, pilotes IA/humains, prévisualisation et animation."""

    def __init__(
        self,
        graph: Graph,
        settings: GameSettings,
        *,
        mode: Mode = Mode.AUTO,
        human_team: Team | None = None,
        stats_store: StatsStore | None = None,
    ) -> None:
        self.graph = graph
        self.settings = settings
        self.rules = settings.to_rules()
        self.game_config = settings.to_game_config()
        self.search = AsyncSearch()
        self.speed = max(0.25, settings.demo_speed)
        self.paused = False
        self.thinking: Team | None = None
        self.last_result: Result | None = None
        self.preview: Move | None = None
        self.selected_police: int | None = None
        self.selected_vertex: str | None = None
        self._pending_animation: Move | None = None
        self._phase = "idle"
        self._timer = 0.0
        self._stepping = False
        self.human_team = human_team
        self.human_teams = self._human_teams(mode, human_team)
        self.mode = Mode.MANUEL if human_team is not None else mode
        self.kind = "demo" if self.mode is Mode.AUTO else "solo"
        if human_team is not None:
            self.stats_mode = "solo"
        elif mode is Mode.AUTO:
            self.stats_mode = "auto"
        else:
            self.stats_mode = "manuel"
        self.stats_store = stats_store or StatsStore()
        self._stats_recorded = False
        self._seed = (
            int(settings.seed) if settings.seed is not None else random.randrange(100_000)
        )
        self.manager = self._new_manager()

    @staticmethod
    def _human_teams(mode: Mode, human_team: Team | None) -> frozenset[Team]:
        if human_team is not None:
            return frozenset((human_team,))
        if mode is Mode.MANUEL:
            return frozenset(Team)
        return frozenset()

    @property
    def mode_name(self) -> str:
        if len(self.human_teams) == 2:
            return "Manuel"
        if self.human_teams:
            return "Solo"
        return "Automatique"

    @property
    def state(self) -> GameState:
        return self.manager.state

    @property
    def is_over(self) -> bool:
        return self.manager.is_over

    @property
    def status(self) -> GameStatus:
        return self.manager.status

    @property
    def ply(self) -> int:
        return self.manager.ply

    @property
    def cooldown_ratio(self) -> float | None:
        if self.rules.return_cooldown <= 0:
            return None
        return min(1.0, self.manager.ply / self.rules.return_cooldown)

    @property
    def legal_count(self) -> int:
        return len(self.manager.legal_moves())

    @property
    def can_human_play(self) -> bool:
        return (
            self.state.turn in self.human_teams
            and not self.is_over
            and not self.search.busy
            and self._pending_animation is None
        )

    def legal_targets(self) -> set[str]:
        if not self.can_human_play:
            return set()
        if self.state.turn is Team.THIEF:
            return {move.dst for move in self.manager.legal_moves()}
        if self.selected_police is None:
            return set()
        return {
            move.dst
            for move in self.manager.legal_moves()
            if move.police_index == self.selected_police
        }

    def take_animation(self) -> Move | None:
        move, self._pending_animation = self._pending_animation, None
        return move

    def _new_manager(self) -> GameManager:
        return GameManager(self.graph, config=self.game_config, seed=self._seed)

    def restart(self) -> None:
        self.search.cancel()
        if self.settings.seed is None:
            self._seed = random.randrange(100_000)
        self.manager = self._new_manager()
        self.thinking = None
        self.last_result = None
        self.preview = None
        self.selected_police = None
        self.selected_vertex = None
        self._pending_animation = None
        self._phase = "idle"
        self._timer = 0.0
        self.paused = False
        self._stepping = False

    def set_paused(self, paused: bool) -> None:
        self.paused = paused
        if not paused:
            self._stepping = False

    def toggle_pause(self) -> None:
        self.set_paused(not self.paused)

    def step_once(self) -> None:
        if self.is_over:
            return
        self._stepping = True
        self._timer = max(self._timer, self._interval())

    def close(self) -> None:
        self.search.shutdown()

    def _interval(self) -> float:
        return max(0.08, DEMO_STEP_DELAY_SECONDS / self.speed)

    def _preview_time(self) -> float:
        return max(0.1, PREVIEW_SECONDS / self.speed)

    def _is_ai_turn(self) -> bool:
        return self.state.turn not in self.human_teams

    def _context(self) -> Context:
        deadline = None
        if self.settings.ai_time_limit > 0:
            deadline = time.perf_counter() + self.settings.ai_time_limit
        return Context(
            rules=self.rules,
            depth=max(1, self.settings.ai_depth),
            repetition_limit=self.settings.repetition_limit,
            history=self.manager.history,
            deadline=deadline,
            stats=Stats(),
            collect_tree=True,
        )

    def _record_stats(self) -> None:
        if self._stats_recorded or not self.is_over:
            return
        self._stats_recorded = True
        self.stats_store.record(self.stats_mode, self.status)

    def update(self, dt: float) -> None:
        self._record_stats()
        if self.is_over or not self._is_ai_turn():
            self._phase = "idle"
            return
        if self.paused and not self._stepping:
            return

        if self._phase == "idle":
            self._phase = "wait"
            if not self._stepping:
                self._timer = 0.0
        if self._phase == "wait":
            self._timer += dt
            if self._timer >= self._interval():
                self._start_search()
        elif self._phase == "search":
            result = self.search.poll()
            if result is not None:
                self.last_result = result
                self.thinking = None
                self.preview = result.move
                self._phase = "preview"
                self._timer = 0.0
        elif self._phase == "preview":
            self._timer += dt
            if self._timer >= self._preview_time():
                self._commit_preview()

    def _start_search(self) -> None:
        if self.search.busy:
            return
        self.thinking = self.state.turn
        self.preview = None
        bot: Bot = police_bot if self.state.turn is Team.POLICE else thief_bot
        self.search.start(bot, self.graph, self.state, self._context(), self.manager.ply)
        self._phase = "search"
        self._timer = 0.0

    def _commit_preview(self) -> None:
        move, self.preview = self.preview, None
        if move is not None and not self.is_over:
            self.manager.play(move)
            self._pending_animation = move
        self._phase = "idle"
        self._timer = 0.0
        if self._stepping:
            self._stepping = False
            self.paused = True

    def handle_board_click(self, vertex: str) -> bool:
        if not self.can_human_play:
            return False
        if self.state.turn is Team.THIEF:
            chosen = next(
                (move for move in self.manager.legal_moves() if move.dst == vertex),
                None,
            )
            if chosen is None:
                self.selected_vertex = None if vertex != self.state.thief else vertex
                return False
            return self._play(chosen)
        if vertex in self.state.police:
            self.selected_police = self.state.police.index(vertex)
            self.selected_vertex = vertex
            return False
        if self.selected_police is None:
            return False
        chosen = next(
            (
                move
                for move in self.manager.legal_moves()
                if move.police_index == self.selected_police and move.dst == vertex
            ),
            None,
        )
        if chosen is None:
            self.selected_police = None
            self.selected_vertex = None
            return False
        return self._play(chosen)

    def _play(self, move: Move) -> bool:
        self.manager.play(move)
        self._pending_animation = move
        self.selected_police = None
        self.selected_vertex = None
        self.preview = None
        self._phase = "idle"
        self._timer = 0.0
        return True

    def status_headline(self) -> str:
        if self.status is GameStatus.POLICE_WIN:
            return "Les trois unités ont fermé toutes les issues."
        if self.status is GameStatus.THIEF_WIN:
            return "Le voleur a atteint le centre du plateau."
        if self.status is GameStatus.DRAW:
            return "Aucun vainqueur : la partie s'arrête."
        return "Partie en cours"

    def status_detail(self) -> str:
        if self.status is GameStatus.POLICE_WIN:
            return "Aucun déplacement légal ne restait au voleur."
        if self.status is GameStatus.THIEF_WIN:
            return f"Centre atteint au demi-coup {self.manager.ply}."
        if self.status is GameStatus.DRAW:
            if self.settings.max_moves > 0 and self.manager.ply >= self.settings.max_moves:
                return "Limite de coups atteinte sans vainqueur."
            return "Position répétée trois fois : nulle par répétition."
        return ""


__all__ = ["MatchController", "Mode", "PREVIEW_SECONDS"]
