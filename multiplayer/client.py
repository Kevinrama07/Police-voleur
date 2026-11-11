"""Client TCP : connexion, réception continue et envoi de messages JSON."""

from __future__ import annotations

import logging
import socket
import threading
from typing import Any, Callable

from multiplayer.protocol import MessageDecoder, ProtocolError, encode

LOGGER = logging.getLogger("police_voleur.client")

RECV_CHUNK = 4096


class NetworkError(RuntimeError):
    """Connexion impossible ou interrompue."""


class GameClient:
    """Se connecte au serveur et livre chaque message décodé à un callback.

    Le callback est exécuté dans le thread réseau : il doit seulement déposer le
    message dans une file, jamais toucher à Pygame.
    """

    def __init__(
        self,
        on_message: Callable[[dict[str, Any]], None],
        on_close: Callable[[str], None] | None = None,
    ) -> None:
        self._on_message = on_message
        self._on_close = on_close
        self._sock: socket.socket | None = None
        self._decoder = MessageDecoder()
        self._send_lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._closing = False
        self._reason = ""

    @property
    def connected(self) -> bool:
        return self._sock is not None and not self._closing

    def connect(self, host: str, port: int, timeout: float = 3.0) -> tuple[str, int]:
        if self._sock is not None:
            raise NetworkError("Une connexion est déjà ouverte.")
        try:
            sock = socket.create_connection((host, int(port)), timeout=timeout)
        except (OSError, ValueError) as exc:
            raise NetworkError(f"Connexion impossible à {host}:{port} — {exc}") from exc
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        sock.settimeout(None)
        self._sock = sock
        self._closing = False
        LOGGER.info("connecté à %s:%s", host, port)
        return sock.getsockname()[:2]  # type: ignore[return-value]

    def start(self) -> None:
        if self._sock is None:
            raise NetworkError("Connectez-vous avant de démarrer la réception.")
        self._thread = threading.Thread(target=self._reader_loop, name="police-client", daemon=True)
        self._thread.start()

    def _reader_loop(self) -> None:
        assert self._sock is not None
        reason = "connexion fermée"
        while not self._closing:
            try:
                chunk = self._sock.recv(RECV_CHUNK)
            except OSError as exc:
                reason = f"erreur réseau ({exc})"
                break
            if not chunk:
                break
            try:
                messages = self._decoder.feed(chunk)
            except ProtocolError as exc:
                self._emit({"type": "ERROR", "code": "protocol_error", "message": str(exc)})
                reason = "flux invalide"
                break
            for error in self._decoder.take_errors():
                self._emit({"type": "ERROR", "code": "malformed_message", "message": error})
            for message in messages:
                self._emit(message)
        self._close_socket()
        if self._reason:
            reason = self._reason
        if self._on_close is not None:
            self._on_close(reason)

    def _emit(self, message: dict[str, Any]) -> None:
        try:
            self._on_message(message)
        except Exception:  # pragma: no cover - un callback ne doit pas tuer le réseau
            LOGGER.exception("callback réseau en erreur")

    def send(self, message: dict[str, Any]) -> bool:
        if self._sock is None or self._closing:
            return False
        try:
            payload = encode(message)
        except ProtocolError:
            LOGGER.exception("message sortant invalide")
            return False
        with self._send_lock:
            try:
                self._sock.sendall(payload)
            except OSError:
                self._reason = "connexion perdue pendant l'envoi"
                self._close_socket()
                return False
        return True

    def close(self, reason: str = "") -> None:
        self._closing = True
        if reason:
            self._reason = reason
        self._close_socket()

    def _close_socket(self) -> None:
        sock, self._sock = self._sock, None
        if sock is None:
            return
        try:
            sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        try:
            sock.close()
        except OSError:
            pass
