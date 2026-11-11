"""Contrôleur commun aux modes hors réseau : tours, IA asynchrone, sélection.

Le mode Démo utilise `human_team = None` (deux IA) ; le mode Solo fournit le camp
du joueur humain. Les règles et l'IA sont exactement celles du moteur commun.
"""

from __future__ import annotations

import random

from ai.minimax import SearchConfig, SearchEngine, SearchResult
from config import DEMO_STEP_DELAY_SECONDS, GameSettings
from core.constants import GameStatus, Team
from core.game_manager import GameConfig, GameManager
from core.game_state import Move
from core.graph import Graph
from core.ruleset import RuleSet
from modes.ai_runner import AsyncSearch

PREVIEW_SECONDS = 0.34


class MatchController:
    """Pilote une partie locale : humain éventuel + IA, animations et prévisualisation."""

    kind = "match"

    def __init__(
        self,
        graph: Graph,
        settings: GameSettings,
        *,
        human_team: Team | None = None,
    ) -> None:
        self.graph = graph
        self.settings = settings
        self.human_team = human_team
        self.rules = RuleSet(
            return_cooldown=settings.return_cooldown,
            center_contestable=settings.center_contestable,
        )
        self.config = SearchConfig(
            max_depth=settings.ai_depth,
            time_limit=settings.ai_time_limit,
            record_tree=True,
            tree_depth=2,
            rules=self.rules,
        )
        self.engine = SearchEngine(graph)
        self.search = AsyncSearch()
        self.speed = max(0.25, settings.demo_speed)
        self.paused = False
        self.thinking: Team | None = None
        self.last_result: SearchResult | None = None
        self.preview: Move | None = None
        self.selected_police: int | None = None
        self.selected_vertex: str | None = None
        self._pending_animation: Move | None = None
        self._phase = "idle"
        self._timer = 0.0
        self._stepping = False
        self._seed = (
            int(settings.seed) if settings.seed is not None else random.randrange(100_000)
        )
        self.manager = self._new_manager()

    # ------------------------------------------------------------------ état exposé

    @property
    def mode_name(self) -> str:
        return "Partie"

    @property
    def state(self):
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
            self.human_team is not None
            and not self.is_over
            and self.state.turn is self.human_team
            and not self.search.busy
            and self._pending_animation is None
        )

    def legal_targets(self) -> set[str]:
        """Sommets cliquables pour l'humain (vide pour l'IA ou hors tour)."""
        if not self.can_human_play:
            return set()
        if self.human_team is Team.THIEF:
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

    # ------------------------------------------------------------------ partie

    def _new_manager(self) -> GameManager:
        config = GameConfig(
            max_moves=self.settings.max_moves,
            repetition_limit=self.settings.repetition_limit,
            rules=self.rules,
        )
        return GameManager(self.graph, config=config, seed=self._seed)

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
        """Avance d'un coup (mode démo) puis se remet en pause."""
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
        return self.human_team is None or self.state.turn is not self.human_team

    # ------------------------------------------------------------------ mise à jour

    def update(self, dt: float) -> None:
        if self.is_over:
            return
        if not self._is_ai_turn():
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
        self.search.start(self.engine, self.state, self.config, self.manager.ply)
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

    # ------------------------------------------------------------------ interactions

    def handle_board_click(self, vertex: str) -> bool:
        """Sélection / déplacement humain ; retourne True si l'état a changé."""
        if not self.can_human_play:
            return False
        if self.human_team is Team.THIEF:
            moves = self.manager.legal_moves()
            chosen = next((move for move in moves if move.dst == vertex), None)
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
        moves = self.manager.legal_moves()
        chosen = next(
            (
                move
                for move in moves
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

    # ------------------------------------------------------------------ résumé

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
