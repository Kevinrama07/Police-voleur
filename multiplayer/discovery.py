"""Découverte des parties POLICE–VOLEUR sur le réseau local."""

from __future__ import annotations

import logging
import socket
import threading
import time
from collections.abc import Callable

LOGGER = logging.getLogger("police_voleur.discovery")

DISCOVERY_PORT = 50506
DISCOVERY_REQUEST = b"POLICE_VOLEUR_DISCOVER_V1"
DISCOVERY_RESPONSE_PREFIX = b"POLICE_VOLEUR_SERVER_V1:"
DISCOVERY_RETRY_INTERVAL = 0.75

StatusProvider = Callable[[], tuple[int, int]]


def _build_response(game_port: int, players: int, started: bool) -> bytes:
    payload = f"{game_port}:{int(players)}:{1 if started else 0}"
    return DISCOVERY_RESPONSE_PREFIX + payload.encode("ascii")


def _parse_response(message: bytes) -> tuple[int, int | None, bool] | None:
    """Décode une réponse ; accepte aussi le format historique « port » seul."""
    if not message.startswith(DISCOVERY_RESPONSE_PREFIX):
        return None
    try:
        payload = message[len(DISCOVERY_RESPONSE_PREFIX) :].decode("ascii")
    except UnicodeDecodeError:
        return None
    parts = payload.split(":")
    try:
        port = int(parts[0])
    except (IndexError, ValueError):
        return None
    if not 0 < port < 65536:
        return None
    players: int | None = None
    started = False
    if len(parts) >= 2:
        try:
            players = int(parts[1])
        except ValueError:
            players = None
    if len(parts) >= 3:
        started = parts[2] == "1"
    return port, players, started


def _local_ipv4_addresses() -> list[str]:
    try:
        infos = socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET)
    except OSError:
        return []
    addresses = {info[4][0] for info in infos if info[4]}
    return sorted(address for address in addresses if not address.startswith("127."))


def _request_targets() -> list[tuple[str, int]]:
    """Cibles de diffusion : limitée, boucle locale et /24 de chaque interface."""
    hosts = {"255.255.255.255", "127.0.0.1"}
    for address in _local_ipv4_addresses():
        octets = address.split(".")
        if len(octets) == 4:
            hosts.add(".".join((*octets[:3], "255")))
    return [(host, DISCOVERY_PORT) for host in sorted(hosts)]


class ServerDiscovery:
    """Répond aux recherches locales avec le port TCP et l'état de la partie."""

    def __init__(self, game_port: int, status: StatusProvider | None = None) -> None:
        self._game_port = game_port
        self._status = status
        self._stopped = threading.Event()
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._socket.bind(("", DISCOVERY_PORT))
            self._socket.settimeout(0.25)
        except OSError:
            self._socket.close()
            raise
        self._thread = threading.Thread(
            target=self._serve, name="police-discovery", daemon=True
        )
        self._thread.start()

    def _current_response(self) -> bytes:
        players, started = 0, 0
        if self._status is not None:
            try:
                players, started = self._status()
            except Exception:  # pragma: no cover - protection du thread réseau
                LOGGER.exception("statut de découverte indisponible")
        return _build_response(self._game_port, int(players), bool(started))

    def _serve(self) -> None:
        while not self._stopped.is_set():
            try:
                message, address = self._socket.recvfrom(128)
            except socket.timeout:
                continue
            except ConnectionResetError:
                continue
            except OSError:
                if not self._stopped.is_set():
                    LOGGER.exception("erreur du service de découverte réseau")
                return
            if message == DISCOVERY_REQUEST:
                try:
                    self._socket.sendto(self._current_response(), address)
                except OSError:
                    if not self._stopped.is_set():
                        LOGGER.exception("impossible de répondre à la découverte réseau")
                    return

    def close(self) -> None:
        self._stopped.set()
        self._socket.close()
        self._thread.join(timeout=1.0)


def find_server(
    timeout: float = 4.0,
    cancelled: threading.Event | None = None,
) -> tuple[str, int] | None:
    """Recherche un serveur joignable ; ignore les parties pleines ou lancées."""
    deadline = time.monotonic() + timeout
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as discovery_socket:
        discovery_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        discovery_socket.settimeout(0.2)
        targets = _request_targets()
        next_request = 0.0
        while time.monotonic() < deadline:
            if cancelled is not None and cancelled.is_set():
                return None
            now = time.monotonic()
            if now >= next_request:
                for target in targets:
                    try:
                        discovery_socket.sendto(DISCOVERY_REQUEST, target)
                    except OSError:
                        continue
                next_request = now + DISCOVERY_RETRY_INTERVAL
            try:
                message, address = discovery_socket.recvfrom(128)
            except socket.timeout:
                continue
            except OSError:
                if cancelled is not None and cancelled.is_set():
                    return None
                raise
            parsed = _parse_response(message)
            if parsed is None:
                continue
            port, players, started = parsed
            if started or (players is not None and players >= 2):
                LOGGER.info("serveur %s:%s ignoré (partie complète ou lancée)", address[0], port)
                continue
            return address[0], port
    return None
