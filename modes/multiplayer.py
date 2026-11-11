"""Mode Multijoueur : miroir autoritaire d'une partie pilotée par le serveur TCP."""

from __future__ import annotations

import logging
from typing import Any

from config import GameSettings
from core.constants import CENTER, GameStatus, Team
from core.game_manager import GameConfig, GameManager
from core.game_rules import GameOverError, legal_moves
from core.game_state import GameState, Move
from core.graph import Graph
from core.ruleset import RuleSet
from multiplayer.network_manager import NetworkManager

LOGGER = logging.getLogger("police_voleur.network")


class NetworkController:
    """État local synchronisé : le serveur décide, le client applique et affiche."""

    kind = "network"

    def __init__(
        self,
        graph: Graph,
        settings: GameSettings,
        network: NetworkManager,
        start_payload: dict[str, Any],
    ) -> None:
        self.graph = graph
        self.settings = settings
        self.network = network
        role = network.role
        if role is None:
            raise ValueError("aucun camp confirmé par le serveur")
        self.human_team: Team = role
        self.rules: RuleSet = settings_to_rules(settings)
        self.config: GameConfig = GameConfig(rules=self.rules)
        seed = int(start_payload.get("seed", 0))
        self.manager = GameManager(
            graph,
            self.config,
            state=GameState.from_dict(start_payload["state"]),
            seed=seed,
        )
        self._total_ply = int(start_payload.get("ply", 0))
        self._status_override: GameStatus | None = None
        self.abandoned = False
        self.connection_lost = False
        self.pending = False
        self.preview: Move | None = None
        self.thinking: Team | None = None
        self.last_result = None
        self.selected_police: int | None = None
        self.selected_vertex: str | None = None
        self.note = "Partie synchronisée avec le serveur."
        self.last_move: Move | None = None
        self._pending_animation: Move | None = None
        self._apply_start(start_payload)

    # ------------------------------------------------------------------ état exposé

    @property
    def mode_name(self) -> str:
        return "Multijoueur"

    @property
    def state(self) -> GameState:
        return self.manager.state

    @property
    def is_over(self) -> bool:
        return self.abandoned or self.status is not GameStatus.ONGOING

    @property
    def status(self) -> GameStatus:
        if self._status_override is not None:
            return self._status_override
        return self.manager.status

    @property
    def ply(self) -> int:
        return self._total_ply

    @property
    def cooldown_ratio(self) -> float | None:
        if self.rules.return_cooldown <= 0:
            return None
        return min(1.0, self._total_ply / self.rules.return_cooldown)

    @property
    def can_human_play(self) -> bool:
        return (
            not self.is_over
            and self.network.connected
            and not self.pending
            and self.state.turn is self.human_team
        )

    def legal_moves(self) -> list[Move]:
        if self.is_over:
            return []
        return legal_moves(self.graph, self.state, self.rules, self._total_ply)

    @property
    def legal_count(self) -> int:
        return len(self.legal_moves())

    def legal_targets(self) -> set[str]:
        if not self.can_human_play:
            return set()
        moves = self.legal_moves()
        if self.human_team is Team.THIEF:
            return {move.dst for move in moves}
        if self.selected_police is None:
            return set()
        return {
            move.dst
            for move in moves
            if move.police_index == self.selected_police
        }

    def take_animation(self) -> Move | None:
        move, self._pending_animation = self._pending_animation, None
        return move

    # ------------------------------------------------------------------ boucle

    def update(self, dt: float) -> None:
        for message in self.network.poll():
            self._handle(message)
        if self.network.peer_left and not self.abandoned:
            self.abandoned = True
            self.pending = False
            self.note = "L'autre joueur a quitté la partie."

    def _handle(self, message: dict[str, Any]) -> None:
        kind = message.get("type")
        if kind == "GAME_STATE":
            self._apply_state(message)
        elif kind == "GAME_START":
            self._apply_start(message)
            self.note = "Nouvelle partie lancée par le serveur."
        elif kind == "MOVE_ACCEPTED":
            self.pending = False
        elif kind == "MOVE_REJECTED":
            self.pending = False
            self.preview = None
            self.note = str(message.get("reason", "Mouvement refusé par le serveur."))
        elif kind == "GAME_OVER":
            status = message.get("status")
            try:
                self._status_override = GameStatus(status)
            except ValueError:
                pass
            self.note = str(message.get("detail", "Partie terminée."))
        elif kind == "PLAYER_DISCONNECTED":
            self.abandoned = True
            self.pending = False
            self.note = "L'autre joueur s'est déconnecté."
        elif kind == "DISCONNECTED":
            self.connection_lost = True
            self.abandoned = True
            self.pending = False
            self.note = "Connexion perdue avec le serveur."
        elif kind == "ERROR":
            self.note = str(message.get("message", "Erreur réseau."))
            LOGGER.warning("erreur serveur : %s", self.note)

    def _apply_start(self, message: dict[str, Any]) -> None:
        rules_data = message.get("rules") or {}
        config_data = message.get("config") or {}
        self.rules = RuleSet(
            return_cooldown=int(rules_data.get("return_cooldown", self.rules.return_cooldown)),
            center_contestable=bool(
                rules_data.get("center_contestable", self.rules.center_contestable)
            ),
        )
        self.config = GameConfig(
            max_moves=int(config_data.get("max_moves", self.config.max_moves)),
            repetition_limit=int(
                config_data.get("repetition_limit", self.config.repetition_limit)
            ),
            rules=self.rules,
        )
        state = GameState.from_dict(message["state"])
        seed = int(message.get("seed", self.manager.seed))
        self.manager = GameManager(self.graph, self.config, state=state, seed=seed)
        self._total_ply = int(message.get("ply", 0))
        self._status_override = None
        self.abandoned = False
        self.connection_lost = False
        self.pending = False
        self.preview = None
        self.selected_police = None
        self.selected_vertex = None
        self.last_move = None
        self._pending_animation = None

    def _apply_state(self, message: dict[str, Any]) -> None:
        try:
            ply = int(message.get("ply", 0))
        except (TypeError, ValueError):
            return
        if ply <= self._total_ply:
            return
        move_data = message.get("move")
        if ply != self._total_ply + 1 or not isinstance(move_data, dict):
            self._resync(message)
            return
        try:
            move = Move.from_dict(move_data)
        except (KeyError, TypeError, ValueError):
            self._resync(message)
            return
        try:
            self.manager.play(move)
        except (GameOverError, ValueError):
            self._resync(message)
            return
        self._total_ply = ply
        self._pending_animation = move
        self.last_move = move
        self.pending = False
        self.preview = None
        try:
            self._status_override = GameStatus(message.get("status"))
        except ValueError:
            self._status_override = None
        self.note = "Synchronisé."

    def _resync(self, message: dict[str, Any]) -> None:
        try:
            state = GameState.from_dict(message["state"])
            ply = int(message.get("ply", 0))
        except (KeyError, TypeError, ValueError):
            return
        self.manager = GameManager(self.graph, self.config, state=state, seed=self.manager.seed)
        self._total_ply = ply
        self.pending = False
        self.preview = None
        try:
            self._status_override = GameStatus(message.get("status"))
        except ValueError:
            self._status_override = None
        self.note = "État resynchronisé avec le serveur."
        LOGGER.info("resynchronisation au demi-coup %s", ply)

    # ------------------------------------------------------------------ interactions

    def handle_board_click(self, vertex: str) -> bool:
        if not self.can_human_play:
            return False
        moves = self.legal_moves()
        if self.human_team is Team.THIEF:
            chosen = next((move for move in moves if move.dst == vertex), None)
            if chosen is None:
                self.selected_vertex = None if vertex != self.state.thief else vertex
                return False
            return self._send_move(chosen)
        if vertex in self.state.police:
            self.selected_police = self.state.police.index(vertex)
            self.selected_vertex = vertex
            return False
        if self.selected_police is None:
            return False
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
        return self._send_move(chosen)

    def _send_move(self, move: Move) -> bool:
        if not self.network.send("MOVE", ply=self._total_ply, move=move.to_dict()):
            self.note = "Connexion perdue : mouvement non envoyé."
            self.connection_lost = True
            return False
        self.pending = True
        self.preview = move
        self.selected_police = None
        self.selected_vertex = None
        self.note = "Mouvement envoyé, en attente du serveur…"
        return True

    def restart(self) -> None:
        if self.abandoned or self.connection_lost:
            self.note = "Impossible de relancer : connexion interrompue."
            return
        if self.network.send("CREATE_GAME"):
            self.note = "Nouvelle partie demandée au serveur…"
        else:
            self.note = "Connexion perdue."

    def close(self) -> None:
        self.network.close()

    # ------------------------------------------------------------------ résumé

    def status_headline(self) -> str:
        if self.status is GameStatus.POLICE_WIN:
            return "Les trois unités ont fermé toutes les issues."
        if self.status is GameStatus.THIEF_WIN:
            return "Le voleur a atteint le centre du plateau."
        if self.status is GameStatus.DRAW:
            return "Aucun vainqueur : la partie s'arrête."
        if self.abandoned:
            return "La partie a été interrompue."
        return "Partie en cours"

    def status_detail(self) -> str:
        if self.abandoned:
            return self.note
        if self.status is GameStatus.POLICE_WIN:
            return "Aucun déplacement légal ne restait au voleur."
        if self.status is GameStatus.THIEF_WIN:
            return f"Centre atteint au demi-coup {self._total_ply}."
        if self.status is GameStatus.DRAW:
            return "Position répétée ou limite de coups atteinte."
        return ""

    def opponent_label(self) -> str:
        for player in self.network.players:
            if player.get("player_id") != self.network.player_id:
                role = player.get("role")
                name = player.get("name") or player.get("player_id")
                if role:
                    return f"{name} · {str(role).upper()}"
                return str(name)
        return "en attente…"


def settings_to_rules(settings: GameSettings) -> RuleSet:
    return RuleSet(
        return_cooldown=settings.return_cooldown,
        center_contestable=settings.center_contestable,
    )
