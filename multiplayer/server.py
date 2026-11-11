"""Serveur TCP autoritaire du mode multijoueur local.

Un seul processus héberge la session (`GameSession`) et accepte deux connexions.
Les clients n'envoient que des intentions ; le serveur valide puis diffuse l'état.

Lancement : ``python -m multiplayer.server`` (options ``--host``, ``--port``, ``--seed``).
"""

from __future__ import annotations

import argparse
import logging
import socket
import threading
from typing import Any

from core.game_manager import GameConfig
from core.graph import build_default_graph
from multiplayer.protocol import (
    PROTOCOL_VERSION,
    MessageDecoder,
    ProtocolError,
    encode,
)
from multiplayer.session import GameSession, SessionError

LOGGER = logging.getLogger("police_voleur.server")

ACCEPT_TIMEOUT = 0.5
RECV_TIMEOUT = 1.0
RECV_CHUNK = 4096


class _Peer:
    """Connexion d'un joueur : envoi sérialisé, réception en continu."""

    def __init__(self, sock: socket.socket, address: tuple[str, int], player_id: str) -> None:
        self.sock = sock
        self.address = address
        self.player_id = player_id
        self.decoder = MessageDecoder()
        self.alive = True
        self._send_lock = threading.Lock()

    def send(self, message: dict[str, Any]) -> bool:
        if not self.alive:
            return False
        try:
            payload = encode(message)
        except ProtocolError:
            LOGGER.exception("message sortant invalide")
            return False
        with self._send_lock:
            try:
                self.sock.sendall(payload)
            except OSError:
                self.alive = False
                return False
        return True

    def close(self) -> None:
        self.alive = False
        try:
            self.sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        try:
            self.sock.close()
        except OSError:
            pass


class GameServer:
    """Serveur TCP : accepte deux joueurs et pilote une `GameSession`."""

    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 0,
        *,
        graph=None,
        config: GameConfig | None = None,
        seed: int = 0,
    ) -> None:
        self._host = host
        self._requested_port = int(port)
        self._graph = graph or build_default_graph()
        self.session = GameSession(self._graph, config or GameConfig(), seed=seed)
        self._socket: socket.socket | None = None
        self._accept_thread: threading.Thread | None = None
        self._lock = threading.RLock()
        self._peers: dict[str, _Peer] = {}
        self._counter = 0
        self._closing = False
        self._port = int(port)

    # ------------------------------------------------------------------ cycle de vie

    @property
    def port(self) -> int:
        return self._port

    @property
    def host(self) -> str:
        return self._host

    @property
    def player_count(self) -> int:
        with self._lock:
            return len(self._peers)

    def start(self) -> tuple[str, int]:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((self._host, self._requested_port))
        sock.listen(4)
        sock.settimeout(ACCEPT_TIMEOUT)
        self._socket = sock
        self._port = sock.getsockname()[1]
        self._closing = False
        self._accept_thread = threading.Thread(
            target=self._accept_loop, name="police-accept", daemon=True
        )
        self._accept_thread.start()
        LOGGER.info("serveur à l'écoute sur %s:%s", self._host, self._port)
        return self._host, self._port

    def stop(self) -> None:
        self._closing = True
        if self._socket is not None:
            try:
                self._socket.close()
            except OSError:
                pass
        with self._lock:
            peers = list(self._peers.values())
            self._peers.clear()
        for peer in peers:
            peer.close()
        if self._accept_thread is not None:
            self._accept_thread.join(timeout=2.0)
            self._accept_thread = None

    # ------------------------------------------------------------------ connexions

    def _accept_loop(self) -> None:
        assert self._socket is not None
        while not self._closing:
            try:
                conn, address = self._socket.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            conn.settimeout(RECV_TIMEOUT)
            conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            self._register(conn, address)

    def _register(self, conn: socket.socket, address: tuple[str, int]) -> None:
        with self._lock:
            if len(self._peers) >= 2:
                peer = _Peer(conn, address, "rejected")
                peer.send(
                    {
                        "type": "ERROR",
                        "code": "server_full",
                        "message": "La partie accepte déjà deux joueurs.",
                    }
                )
                peer.close()
                return
            if self._closing:
                conn.close()
                return
            self._counter += 1
            player_id = f"P{self._counter}"
            try:
                self.session.add_player(player_id, f"Joueur {self._counter}")
            except SessionError as exc:
                conn.close()
                LOGGER.warning("connexion refusée : %s", exc.message)
                return
            peer = _Peer(conn, address, player_id)
            self._peers[player_id] = peer
            LOGGER.info("joueur %s connecté depuis %s:%s", player_id, *address)
            peer.send(
                {
                    "type": "WELCOME",
                    "protocol": PROTOCOL_VERSION,
                    "player_id": player_id,
                    "game_id": self.session.game_id,
                }
            )
            self._broadcast({"type": "JOIN_GAME", "player_id": player_id, **self.session.roster()})
        threading.Thread(
            target=self._reader_loop, args=(peer,), name=f"police-{player_id}", daemon=True
        ).start()

    def _reader_loop(self, peer: _Peer) -> None:
        reason = "connexion fermée"
        while not self._closing and peer.alive:
            try:
                chunk = peer.sock.recv(RECV_CHUNK)
            except socket.timeout:
                continue
            except OSError:
                reason = "erreur réseau"
                break
            if not chunk:
                break
            try:
                messages = peer.decoder.feed(chunk)
            except ProtocolError as exc:
                peer.send({"type": "ERROR", "code": "protocol_error", "message": str(exc)})
                reason = "flux invalide"
                break
            for error in peer.decoder.take_errors():
                peer.send({"type": "ERROR", "code": "malformed_message", "message": error})
            for message in messages:
                self._dispatch(peer, message)
        self._disconnect(peer, reason)

    def _disconnect(self, peer: _Peer, reason: str) -> None:
        with self._lock:
            if self._peers.pop(peer.player_id, None) is None:
                peer.close()
                return
            was_started = self.session.started
            self.session.remove_player(peer.player_id)
            LOGGER.info("joueur %s déconnecté (%s)", peer.player_id, reason)
            peer.close()
            self._broadcast(
                {
                    "type": "PLAYER_DISCONNECTED",
                    "player_id": peer.player_id,
                    "reason": reason,
                    "started": was_started,
                }
            )
            if not was_started:
                self._broadcast({"type": "JOIN_GAME", **self.session.roster()})

    def _broadcast(self, message: dict[str, Any]) -> None:
        dead = [peer for peer in self._peers.values() if not peer.send(message)]
        for peer in dead:
            self._peers.pop(peer.player_id, None)
            peer.close()

    # ------------------------------------------------------------------ messages

    def _dispatch(self, peer: _Peer, message: dict[str, Any]) -> None:
        kind = message.get("type")
        with self._lock:
            try:
                if kind == "PING":
                    peer.send({"type": "PONG"})
                elif kind == "SELECT_ROLE":
                    self._handle_select_role(peer, message)
                elif kind == "MOVE":
                    self._handle_move(peer, message)
                elif kind == "CREATE_GAME":
                    self._handle_create_game(peer, message)
                else:
                    peer.send(
                        {
                            "type": "ERROR",
                            "code": "unknown_message",
                            "message": f"Type de message inconnu : {kind!r}.",
                        }
                    )
            except Exception:  # pragma: no cover - garde-fou du serveur
                LOGGER.exception("erreur interne pendant le traitement de %r", kind)
                peer.send(
                    {
                        "type": "ERROR",
                        "code": "server_error",
                        "message": "Erreur interne du serveur.",
                    }
                )

    def _handle_select_role(self, peer: _Peer, message: dict[str, Any]) -> None:
        role_value = message.get("role")
        try:
            role = self.session.select_role(peer.player_id, str(role_value))
        except SessionError as exc:
            peer.send(
                {
                    "type": "ERROR",
                    "code": exc.code,
                    "message": exc.message,
                    "available_roles": [item.value for item in self.session.available_roles()],
                }
            )
            return
        peer.send({"type": "ROLE_CONFIRMED", "role": role.value, "player_id": peer.player_id})
        self._broadcast({"type": "JOIN_GAME", **self.session.roster()})
        if self.session.both_roles_ready():
            self.session.start()
            LOGGER.info("partie %s lancée", self.session.game_id)
            self._broadcast(self.session.start_message())

    def _handle_create_game(self, peer: _Peer, message: dict[str, Any]) -> None:
        if peer.player_id not in self.session.players:
            peer.send({"type": "ERROR", "code": "unknown_player", "message": "Joueur inconnu."})
            return
        if self.session.started and not self.session.abandoned:
            if self.session.manager is not None and not self.session.manager.is_over:
                peer.send(
                    {
                        "type": "ERROR",
                        "code": "game_running",
                        "message": "La partie est déjà en cours.",
                    }
                )
                return
        requested = message.get("seed")
        try:
            seed = None if requested is None else int(requested)
        except (TypeError, ValueError):
            seed = None
        if not self.session.started:
            peer.send(
                {
                    "type": "ERROR",
                    "code": "roles_missing",
                    "message": "Attendez que les deux joueurs aient choisi un camp.",
                }
            )
            return
        try:
            self.session.rematch(seed)
        except SessionError as exc:
            peer.send({"type": "ERROR", "code": exc.code, "message": exc.message})
            return
        self._broadcast(self.session.start_message())

    def _handle_move(self, peer: _Peer, message: dict[str, Any]) -> None:
        try:
            move = self.session.apply_move(
                peer.player_id, message.get("move"), message.get("ply")
            )
        except SessionError as exc:
            LOGGER.info("coup refusé (%s) : %s", exc.code, exc.message)
            peer.send(
                {
                    "type": "MOVE_REJECTED",
                    "code": exc.code,
                    "reason": exc.message,
                    "ply": None if self.session.manager is None else self.session.manager.ply,
                }
            )
            return
        peer.send(
            {
                "type": "MOVE_ACCEPTED",
                "move": move.to_dict(),
                "ply": self.session.manager.ply,
            }
        )
        self._broadcast(self.session.state_message())
        assert self.session.manager is not None
        if self.session.manager.is_over:
            self._broadcast(self.session.over_message())


def local_ip() -> str:
    """Adresse IPv4 locale utilisée pour joindre le réseau (sans trafic émis)."""
    try:
        probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            probe.connect(("8.8.8.8", 80))
            return probe.getsockname()[0]
        finally:
            probe.close()
    except OSError:
        return "127.0.0.1"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Serveur POLICE – VOLEUR (réseau local)")
    parser.add_argument("--host", default="0.0.0.0", help="interface d'écoute (défaut : toutes)")
    parser.add_argument("--port", type=int, default=50505, help="port TCP (défaut : 50505)")
    parser.add_argument("--seed", type=int, default=0, help="graine de la première partie")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(message)s", datefmt="%H:%M:%S")
    server = GameServer(args.host, args.port, seed=args.seed)
    address = local_ip()
    try:
        server.start()
    except OSError as exc:
        print(f"Impossible d'ouvrir le port {args.port} : {exc}")
        return 1
    print("POLICE – VOLEUR · serveur multijoueur")
    print(f"Écoute sur {args.host}:{server.port}")
    print(f"Adresse à communiquer : {address}:{server.port}")
    print("Ctrl+C pour arrêter.\n")
    try:
        while True:
            threading.Event().wait(0.5)
    except KeyboardInterrupt:
        print("\nArrêt du serveur.")
    finally:
        server.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
