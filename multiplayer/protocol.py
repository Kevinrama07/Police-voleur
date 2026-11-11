"""Protocole réseau : messages JSON délimités par des sauts de ligne (NDJSON).

Chaque message est un objet JSON sur une seule ligne, encodé en UTF-8 et terminé
par ``\\n``. Le découpage par ligne rend la détection des messages incomplets
triviale : un tampon conserve les octets non terminés entre deux lectures.
"""

from __future__ import annotations

import json
from typing import Any, Mapping

PROTOCOL_VERSION = 1
MAX_MESSAGE_BYTES = 65_536
MAX_BUFFER_BYTES = 1_048_576

MESSAGE_TYPES = (
    "CREATE_GAME",
    "JOIN_GAME",
    "SELECT_ROLE",
    "ROLE_CONFIRMED",
    "GAME_START",
    "MOVE",
    "MOVE_ACCEPTED",
    "MOVE_REJECTED",
    "GAME_STATE",
    "GAME_OVER",
    "PLAYER_DISCONNECTED",
    "ERROR",
    "WELCOME",
    "PING",
    "PONG",
)


class ProtocolError(ValueError):
    """Message réseau invalide (trop gros, JSON illisible, type absent)."""


def encode(message: Mapping[str, Any]) -> bytes:
    """Sérialise un message en une ligne JSON terminée par ``\\n``."""
    try:
        payload = json.dumps(message, separators=(",", ":"), ensure_ascii=False)
    except (TypeError, ValueError) as exc:
        raise ProtocolError(f"message non sérialisable : {exc}") from exc
    data = payload.encode("utf-8")
    if len(data) > MAX_MESSAGE_BYTES:
        raise ProtocolError("message trop volumineux")
    return data + b"\n"


def decode_line(line: bytes) -> dict[str, Any]:
    """Décode une ligne complète et vérifie la présence d'un type valide."""
    try:
        message = json.loads(line.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ProtocolError(f"JSON invalide : {exc}") from exc
    if not isinstance(message, dict):
        raise ProtocolError("le message doit être un objet JSON")
    if not isinstance(message.get("type"), str) or not message["type"]:
        raise ProtocolError("type de message manquant")
    return message


class MessageDecoder:
    """Assemble les flux TCP en messages complets, ignore les lignes invalides."""

    def __init__(self, max_message: int = MAX_MESSAGE_BYTES, max_buffer: int = MAX_BUFFER_BYTES) -> None:
        self._buffer = bytearray()
        self._max_message = max_message
        self._max_buffer = max_buffer
        self.errors: list[str] = []

    def feed(self, chunk: bytes) -> list[dict[str, Any]]:
        """Ajoute des octets et retourne les messages complets (les erreurs sont listées)."""
        self._buffer.extend(chunk)
        messages: list[dict[str, Any]] = []
        while True:
            index = self._buffer.find(b"\n")
            if index < 0:
                break
            line = bytes(self._buffer[:index])
            del self._buffer[: index + 1]
            if not line.strip():
                continue
            if len(line) > self._max_message:
                self.errors.append("ligne trop longue")
                continue
            try:
                messages.append(decode_line(line))
            except ProtocolError as exc:
                self.errors.append(str(exc))
        if len(self._buffer) > self._max_buffer:
            raise ProtocolError("tampon réseau saturé : message incomplet trop volumineux")
        return messages

    def take_errors(self) -> list[str]:
        errors, self.errors = self.errors, []
        return errors
