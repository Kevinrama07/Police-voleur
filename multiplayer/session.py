"""Session de jeu autoritaire (sans socket) : rôles, tours et validation des coups.

Le serveur ne fait que transporter : toute décision de jeu est prise ici, puis
diffusée aux clients sous forme d'états complets.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

from core.constants import GameStatus, Team
from core.game_manager import GameConfig, GameManager
from core.game_rules import legal_moves
from core.game_state import GameState, Move
from core.graph import Graph
from core.ruleset import RuleSet

MAX_PLAYERS = 2

STATUS_DETAILS = {
    GameStatus.POLICE_WIN: "Les trois policiers ont bloqué le voleur.",
    GameStatus.THIEF_WIN: "Le voleur a regagné le centre.",
    GameStatus.DRAW: "Aucun vainqueur (répétition ou limite de coups).",
    GameStatus.ONGOING: "Partie en cours.",
}


class SessionError(RuntimeError):
    """Refus explicite d'une intention client (mouvement, rôle, partie)."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(slots=True)
class PlayerSlot:
    player_id: str
    name: str
    role: Team | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "player_id": self.player_id,
            "name": self.name,
            "role": None if self.role is None else self.role.value,
        }


class GameSession:
    """État complet d'une partie réseau, réinitialisable (revanche)."""

    def __init__(
        self,
        graph: Graph,
        config: GameConfig | None = None,
        seed: int = 0,
    ) -> None:
        self.graph = graph
        self.config = config or GameConfig()
        self.seed = int(seed)
        self.game_id = uuid4().hex[:8]
        self.players: dict[str, PlayerSlot] = {}
        self.manager: GameManager | None = None
        self.started = False
        self.abandoned = False
        self.last_move: Move | None = None

    # ------------------------------------------------------------------ joueurs

    @property
    def rules(self) -> RuleSet:
        return self.config.rules

    def add_player(self, player_id: str, name: str) -> PlayerSlot:
        if len(self.players) >= MAX_PLAYERS:
            raise SessionError("server_full", "La partie accepte déjà deux joueurs.")
        slot = PlayerSlot(player_id=player_id, name=name or player_id)
        self.players[player_id] = slot
        return slot

    def remove_player(self, player_id: str) -> bool:
        slot = self.players.pop(player_id, None)
        if slot is None:
            return False
        if self.started:
            self.abandoned = True
            self.started = False
        return True

    def role_of(self, player_id: str) -> Team | None:
        slot = self.players.get(player_id)
        return None if slot is None else slot.role

    def role_owner(self, role: Team) -> PlayerSlot | None:
        return next((slot for slot in self.players.values() if slot.role is role), None)

    def available_roles(self) -> tuple[Team, ...]:
        taken = {slot.role for slot in self.players.values()}
        return tuple(role for role in (Team.POLICE, Team.THIEF) if role not in taken)

    def select_role(self, player_id: str, role_value: str) -> Team:
        slot = self.players.get(player_id)
        if slot is None:
            raise SessionError("unknown_player", "Joueur inconnu.")
        if self.started:
            raise SessionError("game_started", "La partie a déjà commencé.")
        try:
            role = Team(role_value)
        except ValueError as exc:
            raise SessionError("invalid_role", f"Rôle inconnu : {role_value!r}.") from exc
        owner = self.role_owner(role)
        if owner is not None and owner.player_id != player_id:
            label = "POLICE" if role is Team.POLICE else "VOLEUR"
            raise SessionError(
                "role_conflict",
                f"Le camp {label} est déjà choisi par l'autre joueur.",
            )
        slot.role = role
        return role

    def both_roles_ready(self) -> bool:
        roles = [slot.role for slot in self.players.values()]
        return (
            len(self.players) == MAX_PLAYERS
            and all(role is not None for role in roles)
            and len(set(roles)) == MAX_PLAYERS
        )

    # ------------------------------------------------------------------ partie

    def start(self) -> GameManager:
        if not self.both_roles_ready():
            raise SessionError("roles_missing", "Les deux joueurs doivent choisir un camp distinct.")
        self.manager = GameManager(self.graph, self.config, seed=self.seed)
        self.started = True
        self.abandoned = False
        self.last_move = None
        return self.manager

    def rematch(self, seed: int | None = None) -> GameManager:
        self.seed = int(seed) if seed is not None else self.seed + 1
        self.started = False
        manager = self.start()
        return manager

    def apply_move(self, player_id: str, move_data: object, ply: object = None) -> Move:
        if self.manager is None or not self.started:
            raise SessionError("not_started", "La partie n'a pas encore commencé.")
        if self.abandoned:
            raise SessionError("abandoned", "La partie a été interrompue.")
        slot = self.players.get(player_id)
        if slot is None:
            raise SessionError("unknown_player", "Joueur inconnu.")
        if slot.role is None:
            raise SessionError("no_role", "Choisissez d'abord un camp.")
        if slot.role is not self.manager.state.turn:
            raise SessionError("not_your_turn", "Ce n'est pas votre tour.")
        server_ply = self.manager.ply
        if ply is not None:
            try:
                client_ply = int(ply)
            except (TypeError, ValueError) as exc:
                raise SessionError("malformed_move", "Numéro de demi-coup invalide.") from exc
            if client_ply != server_ply:
                raise SessionError(
                    "stale_move",
                    f"Demi-coup attendu : {server_ply}, reçu : {client_ply}.",
                )
        try:
            intended = Move.from_dict(move_data)  # type: ignore[arg-type]
        except (KeyError, TypeError, ValueError) as exc:
            raise SessionError("malformed_move", f"Mouvement illisible : {exc}") from exc
        legal = legal_moves(self.graph, self.manager.state, self.rules, server_ply)
        if intended not in legal:
            raise SessionError("illegal_move", "Ce mouvement n'est pas autorisé par les règles.")
        self.manager.play(intended)
        self.last_move = intended
        return intended

    # ------------------------------------------------------------------ messages

    def roster(self) -> dict[str, object]:
        return {
            "players": [slot.to_dict() for slot in self.players.values()],
            "available_roles": [role.value for role in self.available_roles()],
            "started": self.started,
            "game_id": self.game_id,
            "max_players": MAX_PLAYERS,
        }

    def start_message(self) -> dict[str, object]:
        assert self.manager is not None
        return {
            "type": "GAME_START",
            "game_id": self.game_id,
            "state": self.manager.state.to_dict(),
            "ply": self.manager.ply,
            "turn": self.manager.state.turn.value,
            "players": [slot.to_dict() for slot in self.players.values()],
            "seed": self.seed,
            "rules": {
                "return_cooldown": self.rules.return_cooldown,
                "center_contestable": self.rules.center_contestable,
            },
            "config": {
                "max_moves": self.config.max_moves,
                "repetition_limit": self.config.repetition_limit,
            },
        }

    def state_message(self) -> dict[str, object]:
        assert self.manager is not None
        return {
            "type": "GAME_STATE",
            "game_id": self.game_id,
            "state": self.manager.state.to_dict(),
            "ply": self.manager.ply,
            "turn": self.manager.state.turn.value,
            "status": self.manager.status.value,
            "move": None if self.last_move is None else self.last_move.to_dict(),
        }

    def over_message(self) -> dict[str, object]:
        assert self.manager is not None
        status = self.manager.status
        return {
            "type": "GAME_OVER",
            "game_id": self.game_id,
            "status": status.value,
            "ply": self.manager.ply,
            "detail": STATUS_DETAILS[status],
        }

    def state_from_dict(self, data) -> GameState:  # pragma: no cover - utilitaire
        return GameState.from_dict(data)
