"""Façade réseau pour l'interface : hébergement, connexion, file de messages.

Les messages sont déposés dans une `Queue` par le thread réseau puis consommés par
la boucle Pygame (`poll`). Aucune fonction de dessin n'est appelée ici.
"""

from __future__ import annotations

import logging
import queue
import threading
from typing import Any

from core.constants import Team
from core.game_manager import GameConfig
from multiplayer.client import GameClient, NetworkError
from multiplayer.discovery import ServerDiscovery, find_server
from multiplayer.server import GameServer, local_ip

LOGGER = logging.getLogger("police_voleur.network")


class NetworkManager:
    """État de la connexion et transport des messages pour les écrans Pygame."""

    def __init__(self) -> None:
        self._server: GameServer | None = None
        self._client: GameClient | None = None
        self._discovery: ServerDiscovery | None = None
        self._messages: queue.Queue[dict[str, Any]] = queue.Queue()
        self._generation = 0
        self.state = "idle"
        self.error = ""
        self.player_id: str | None = None
        self.game_id: str = ""
        self.role: Team | None = None
        self.players: list[dict[str, Any]] = []
        self.available_roles: tuple[Team, ...] = (Team.POLICE, Team.THIEF)
        self.started = False
        self.peer_left = False
        self.server_address: tuple[str, int] | None = None
        self.join_address: tuple[str, int] | None = None
        self.discovery_error = ""

    # ------------------------------------------------------------------ propriétés

    @property
    def connected(self) -> bool:
        return self.state in {"connected", "connecting"} and self._client is not None

    @property
    def is_host(self) -> bool:
        return self._server is not None

    @property
    def local_address(self) -> str:
        """Adresse lisible à communiquer à l'autre joueur (hôte uniquement)."""
        if self.server_address is None:
            return ""
        return f"{self.server_address[0]}:{self.server_address[1]}"

    def role_label(self) -> str:
        if self.role is Team.POLICE:
            return "POLICE"
        if self.role is Team.THIEF:
            return "VOLEUR"
        return "—"

    # ------------------------------------------------------------------ connexion

    def host(
        self,
        port: int = 0,
        *,
        seed: int = 0,
        config: GameConfig | None = None,
    ) -> tuple[str, int]:
        """Démarre un serveur embarqué puis s'y connecte comme un client normal."""
        self.close()
        server = GameServer("0.0.0.0", port, config=config, seed=seed)
        try:
            server.start()
        except OSError as exc:
            self.state = "error"
            self.error = f"Impossible d'ouvrir le port {port} : {exc}"
            raise NetworkError(self.error) from exc
        lan = local_ip()
        self._server = server
        self.server_address = (lan, server.port)
        self.discovery_error = ""
        try:
            self._discovery = ServerDiscovery(server.port, status=self._discovery_status)
        except OSError as exc:
            self._discovery = None
            self.discovery_error = (
                f"Découverte automatique indisponible ({exc}). "
                "Communiquez l'adresse affichée et utilisez la connexion directe."
            )
            LOGGER.warning("découverte UDP indisponible : %s", exc)
        try:
            self.join("127.0.0.1", server.port)
        except NetworkError:
            self._stop_discovery()
            self._server = None
            server.stop()
            self.server_address = None
            self.discovery_error = ""
            raise
        LOGGER.info("hébergement sur %s:%s", lan, server.port)
        return self.server_address

    def _discovery_status(self) -> tuple[int, int]:
        server = self._server
        if server is None:
            return 0, 0
        session = getattr(server, "session", None)
        started = 1 if session is not None and session.started else 0
        return server.player_count, started

    def join(self, host: str, port: int, timeout: float = 3.0) -> None:
        self._disconnect_client()
        self.state = "connecting"
        self.error = ""
        self.players = []
        self.started = False
        self.role = None
        self.peer_left = False
        generation = self._generation
        client = GameClient(
            lambda message: self._on_message(message, generation),
            lambda reason: self._on_close(reason, generation),
        )
        try:
            client.connect(host, int(port), timeout=timeout)
        except NetworkError as exc:
            self.state = "error"
            self.error = str(exc)
            raise
        self._client = client
        self.state = "connected"
        self.join_address = (host, int(port))
        client.start()

    def join_discovered(
        self,
        timeout: float = 4.0,
        cancelled: threading.Event | None = None,
    ) -> tuple[str, int] | None:
        """Trouve automatiquement un hôte local puis s'y connecte."""
        try:
            address = find_server(timeout, cancelled)
        except OSError as exc:
            self.state = "error"
            self.error = f"Recherche réseau impossible : {exc}"
            raise NetworkError(self.error) from exc
        if address is None:
            return None
        if cancelled is not None and cancelled.is_set():
            return None
        self.join(*address)
        if cancelled is not None and cancelled.is_set():
            self.close()
            return None
        return address

    def send(self, kind: str, **payload: Any) -> bool:
        if self._client is None or not self._client.connected:
            self.error = "Connexion fermée."
            return False
        return self._client.send({"type": kind, **payload})

    def poll(self) -> list[dict[str, Any]]:
        messages: list[dict[str, Any]] = []
        while True:
            try:
                messages.append(self._messages.get_nowait())
            except queue.Empty:
                break
        return messages

    def _disconnect_client(self, reason: str = "fermeture locale") -> None:
        self._generation += 1
        client, self._client = self._client, None
        if client is not None:
            client.close(reason)

    def close(self) -> None:
        self._disconnect_client()
        self._stop_discovery()
        server, self._server = self._server, None
        if server is not None:
            server.stop()
        if self.state != "error":
            self.state = "idle"
        self.players = []
        self.started = False
        self.role = None
        self.player_id = None
        self.game_id = ""
        self.server_address = None
        self.join_address = None
        self.peer_left = False
        self.discovery_error = ""

    def _stop_discovery(self) -> None:
        discovery, self._discovery = self._discovery, None
        if discovery is not None:
            discovery.close()

    # ------------------------------------------------------------------ réception

    def _on_message(self, message: dict[str, Any], generation: int | None = None) -> None:
        if generation is not None and generation != self._generation:
            return
        kind = message.get("type")
        if kind == "WELCOME":
            self.player_id = message.get("player_id")
            self.game_id = str(message.get("game_id", ""))
        elif kind == "JOIN_GAME":
            self.players = list(message.get("players", []))
            self.available_roles = tuple(
                Team(value)
                for value in message.get("available_roles", [])
                if value in {team.value for team in Team}
            )
            self.started = bool(message.get("started", False))
            self.game_id = str(message.get("game_id", self.game_id))
        elif kind == "ROLE_CONFIRMED":
            role_value = message.get("role")
            try:
                self.role = Team(role_value)
            except (TypeError, ValueError):
                self.role = None
            self.error = ""
        elif kind == "GAME_START":
            self.started = True
            self.game_id = str(message.get("game_id", self.game_id))
            self.peer_left = False
            role = self.role
            if role is None:
                for player in message.get("players", []):
                    if player.get("player_id") == self.player_id and player.get("role"):
                        try:
                            self.role = Team(player["role"])
                        except ValueError:
                            pass
        elif kind == "PLAYER_DISCONNECTED":
            self.peer_left = True
        elif kind == "ERROR":
            self.error = str(message.get("message", "Erreur réseau inconnue."))
        elif kind == "DISCONNECTED":
            self.state = "closed"
            if not self.error:
                self.error = str(message.get("reason", "Connexion perdue."))
        self._messages.put(message)

    def _on_close(self, reason: str, generation: int | None = None) -> None:
        if generation is not None and generation != self._generation:
            return
        if self.state != "idle":
            self.state = "closed"
        if reason and reason != "fermeture locale" and not self.error:
            self.error = reason
        self._messages.put({"type": "DISCONNECTED", "reason": reason})
