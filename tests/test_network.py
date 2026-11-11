"""Tests du protocole, de la session autoritaire et du transport TCP local."""

from __future__ import annotations

import socket
import threading
import time
from types import SimpleNamespace
from typing import Any, Callable

import pygame
import pytest

from config import GameSettings, WINDOW_SIZE
from core.constants import Team
from core.game_manager import GameConfig
from core.game_rules import legal_moves
from core.game_state import GameState, Move
from core.graph import build_default_graph
from multiplayer.client import GameClient
from multiplayer.network_manager import NetworkManager
from multiplayer.protocol import (
    MAX_BUFFER_BYTES,
    MessageDecoder,
    ProtocolError,
    decode_line,
    encode,
)
from multiplayer.server import GameServer
from multiplayer.session import GameSession, SessionError
from interface.screens.network_setup import NetworkSetup, split_address
from interface.theme import Fonts

GRAPH = build_default_graph()


# ---------------------------------------------------------------------- helpers


class ClientHarness:
    """Client de test : collecte les messages reçus dans une liste protégée."""

    def __init__(self) -> None:
        self.messages: list[dict[str, Any]] = []
        self.lock = threading.Lock()
        self.closed = threading.Event()
        self.close_reason = ""
        self.client = GameClient(self._on_message, self._on_close)
        self.player_id = ""

    def _on_message(self, message: dict[str, Any]) -> None:
        with self.lock:
            self.messages.append(message)

    def _on_close(self, reason: str) -> None:
        self.close_reason = reason
        self.closed.set()

    def connect(self, port: int) -> None:
        self.client.connect("127.0.0.1", port, timeout=3.0)
        self.client.start()
        welcome = self.wait("WELCOME")
        self.player_id = welcome["player_id"]

    def send(self, kind: str, **payload: Any) -> bool:
        return self.client.send({"type": kind, **payload})

    def wait(
        self,
        kind: str,
        predicate: Callable[[dict[str, Any]], bool] | None = None,
        timeout: float = 4.0,
    ) -> dict[str, Any]:
        deadline = time.time() + timeout
        while time.time() < deadline:
            with self.lock:
                for index, message in enumerate(self.messages):
                    if message.get("type") == kind and (
                        predicate is None or predicate(message)
                    ):
                        return self.messages.pop(index)
            time.sleep(0.005)
        with self.lock:
            snapshot = list(self.messages)
        raise AssertionError(f"message {kind!r} non reçu ; reçus : {snapshot}")

    def close(self) -> None:
        self.client.close("fin de test")


class LineReader:
    def __init__(self, sock: socket.socket) -> None:
        self.sock = sock
        self.buffer = b""

    def line(self, timeout: float = 3.0) -> dict[str, Any] | None:
        self.sock.settimeout(timeout)
        while b"\n" not in self.buffer:
            try:
                chunk = self.sock.recv(4096)
            except socket.timeout:
                return None
            if not chunk:
                return None
            self.buffer += chunk
        line, self.buffer = self.buffer.split(b"\n", 1)
        return decode_line(line)

    def wait_type(self, kind: str, timeout: float = 3.0) -> dict[str, Any] | None:
        deadline = time.time() + timeout
        while time.time() < deadline:
            message = self.line(timeout=max(0.05, deadline - time.time()))
            if message is not None and message.get("type") == kind:
                return message
        return None


@pytest.fixture()
def live_server():
    server = GameServer("127.0.0.1", 0, seed=11)
    _, port = server.start()
    clients: list[ClientHarness] = []

    def make_client() -> ClientHarness:
        client = ClientHarness()
        client.connect(port)
        clients.append(client)
        return client

    try:
        yield server, port, make_client
    finally:
        for client in clients:
            client.close()
        server.stop()


def initial_session() -> GameSession:
    session = GameSession(GRAPH, GameConfig(), seed=5)
    session.add_player("P1", "Alice")
    session.add_player("P2", "Bob")
    return session


def legal_thief_moves(session: GameSession) -> list[Move]:
    assert session.manager is not None
    return [
        move
        for move in legal_moves(GRAPH, session.manager.state, session.rules, session.manager.ply)
        if move.team is Team.THIEF
    ]


def legal_police_moves(session: GameSession) -> list[Move]:
    assert session.manager is not None
    return [
        move
        for move in legal_moves(GRAPH, session.manager.state, session.rules, session.manager.ply)
        if move.team is Team.POLICE
    ]


# ---------------------------------------------------------------------- protocole


def test_encode_decode_round_trip() -> None:
    payload = {"type": "MOVE", "ply": 3, "move": {"src": "CENTER", "dst": "VCt"}}
    data = encode(payload)
    assert data.endswith(b"\n")
    assert decode_line(data.strip()) == payload


def test_encode_rejects_oversized_message() -> None:
    with pytest.raises(ProtocolError):
        encode({"type": "PING", "blob": "x" * 70_000})


def test_decoder_reassembles_fragmented_stream() -> None:
    decoder = MessageDecoder()
    data = encode({"type": "PING", "id": 1}) + encode({"type": "PING", "id": 2})
    assert decoder.feed(data[:7]) == []
    assert decoder.feed(data[7:20]) == []
    messages = decoder.feed(data[20:])
    assert [message["id"] for message in messages] == [1, 2]


def test_decoder_reports_invalid_lines_without_crashing() -> None:
    decoder = MessageDecoder()
    messages = decoder.feed(b'{"type":"PING"}\nnot json\n{"nope":1}\n')
    assert len(messages) == 1
    assert len(decoder.take_errors()) == 2
    assert decoder.take_errors() == []


def test_decoder_rejects_saturated_buffer() -> None:
    decoder = MessageDecoder(max_message=100, max_buffer=250)
    with pytest.raises(ProtocolError):
        decoder.feed(b"x" * 300)


def test_decoder_flags_line_above_limit() -> None:
    decoder = MessageDecoder(max_message=40)
    assert decoder.feed(encode({"type": "PING", "pad": "x" * 60})) == []
    assert "ligne trop longue" in decoder.take_errors()


# ---------------------------------------------------------------------- session


def test_session_accepts_two_players_only() -> None:
    session = initial_session()
    with pytest.raises(SessionError) as info:
        session.add_player("P3", "Carol")
    assert info.value.code == "server_full"


def test_session_role_conflict_and_availability() -> None:
    session = initial_session()
    assert session.available_roles() == (Team.POLICE, Team.THIEF)
    session.select_role("P1", "police")
    assert session.available_roles() == (Team.THIEF,)
    with pytest.raises(SessionError) as info:
        session.select_role("P2", "police")
    assert info.value.code == "role_conflict"
    assert session.select_role("P2", "thief") is Team.THIEF
    assert session.both_roles_ready()
    session.start()
    with pytest.raises(SessionError) as info:
        session.select_role("P2", "thief")
    assert info.value.code == "game_started"


def test_session_move_validation() -> None:
    session = initial_session()
    session.select_role("P1", "police")
    session.select_role("P2", "thief")
    with pytest.raises(SessionError) as info:
        session.apply_move("P2", {"team": "thief", "src": "CENTER", "dst": "VCt"})
    assert info.value.code == "not_started"
    session.start()
    with pytest.raises(SessionError) as info:
        session.apply_move(
            "P1", {"team": "police", "src": "EARb", "dst": "T", "police_index": 0}, 0
        )
    assert info.value.code == "not_your_turn"
    with pytest.raises(SessionError) as info:
        session.apply_move("P2", {"team": "thief", "src": "CENTER", "dst": "B"}, 0)
    assert info.value.code == "illegal_move"
    with pytest.raises(SessionError) as info:
        session.apply_move("P2", {"team": "thief", "src": "CENTER", "dst": "VCt"}, 9)
    assert info.value.code == "stale_move"
    with pytest.raises(SessionError) as info:
        session.apply_move("P2", "pas un mouvement", 0)
    assert info.value.code == "malformed_move"
    move = legal_thief_moves(session)[0]
    assert session.apply_move("P2", move.to_dict(), 0) == move
    assert session.manager is not None and session.manager.ply == 1


def test_session_abandon_allows_rejoin_and_rematch() -> None:
    session = initial_session()
    session.select_role("P1", "police")
    session.select_role("P2", "thief")
    session.start()
    assert session.remove_player("P2")
    assert session.abandoned and not session.started
    with pytest.raises(SessionError) as info:
        session.apply_move("P1", {"team": "police", "src": "T", "dst": "J1"}, 0)
    assert info.value.code == "not_started"
    session.add_player("P3", "Carol")
    session.select_role("P3", "thief")
    session.rematch(seed=99)
    assert session.started and not session.abandoned
    assert session.manager is not None and session.manager.seed == 99


def test_start_requires_distinct_roles() -> None:
    session = initial_session()
    with pytest.raises(SessionError) as info:
        session.start()
    assert info.value.code == "roles_missing"
    assert session.manager is None


# ---------------------------------------------------------------------- intégration


def test_server_assigns_players_and_roles(live_server) -> None:
    server, _port, make_client = live_server
    alice = make_client()
    bob = make_client()
    assert alice.player_id == "P1" and bob.player_id == "P2"
    roster = alice.wait("JOIN_GAME", lambda message: len(message["players"]) == 2)
    assert {player["player_id"] for player in roster["players"]} == {"P1", "P2"}

    alice.send("SELECT_ROLE", role="police")
    assert alice.wait("ROLE_CONFIRMED")["role"] == "police"
    bob.send("SELECT_ROLE", role="police")
    error = bob.wait("ERROR")
    assert error["code"] == "role_conflict"

    bob.send("SELECT_ROLE", role="thief")
    alice_start = alice.wait("GAME_START")
    bob_start = bob.wait("GAME_START")
    assert alice_start["state"] == bob_start["state"]
    assert alice_start["ply"] == 0
    assert alice_start["state"]["turn"] == "thief"


def test_server_arbitrates_full_turn(live_server) -> None:
    server, _port, make_client = live_server
    alice = make_client()
    bob = make_client()
    alice.send("SELECT_ROLE", role="police")
    alice.wait("ROLE_CONFIRMED")
    bob.send("SELECT_ROLE", role="thief")
    bob.wait("ROLE_CONFIRMED")
    start = bob.wait("GAME_START")
    alice.wait("GAME_START")

    session = server.session
    assert session.manager is not None
    thief_move = legal_thief_moves(session)[0]
    assert bob.send("MOVE", ply=0, move=thief_move.to_dict())
    state = alice.wait("GAME_STATE", lambda message: message["ply"] == 1)
    assert state["status"] == "ongoing"
    bob.wait("GAME_STATE", lambda message: message["ply"] == 1)

    police_move = legal_police_moves(session)[0]
    alice.send("MOVE", ply=1, move=police_move.to_dict())
    alice.wait("GAME_STATE", lambda message: message["ply"] == 2)
    bob.wait("GAME_STATE", lambda message: message["ply"] == 2)

    alice.send("MOVE", ply=2, move=police_move.to_dict())
    rejected = alice.wait("MOVE_REJECTED")
    assert rejected["code"] == "not_your_turn"

    bob.send("MOVE", ply=0, move=thief_move.to_dict())
    stale = bob.wait("MOVE_REJECTED")
    assert stale["code"] == "stale_move"


def test_server_rejects_third_player(live_server) -> None:
    server, port, make_client = live_server
    make_client()
    make_client()
    raw = socket.create_connection(("127.0.0.1", port), timeout=3.0)
    try:
        message = LineReader(raw).line()
        assert message is not None and message["type"] == "ERROR"
        assert message["code"] == "server_full"
    finally:
        raw.close()


def test_server_handles_fragmented_and_malformed_input(live_server) -> None:
    server, port, _make_client = live_server
    raw = socket.create_connection(("127.0.0.1", port), timeout=3.0)
    reader = LineReader(raw)
    try:
        assert reader.line()["type"] == "WELCOME"
        raw.sendall(b'{"type":"PI')
        time.sleep(0.05)
        raw.sendall(b'NG"}\n')
        assert reader.wait_type("PONG") is not None

        raw.sendall(b"ceci n'est pas du json\n")
        error = reader.wait_type("ERROR")
        assert error is not None and error["code"] == "malformed_message"

        raw.sendall(b'{"type":"PING","pad":"' + b"x" * 70_000 + b'"}\n')
        oversize = reader.wait_type("ERROR")
        assert oversize is not None and oversize["code"] == "malformed_message"
    finally:
        raw.close()


def test_server_notifies_disconnection(live_server) -> None:
    server, _port, make_client = live_server
    alice = make_client()
    bob = make_client()
    alice.send("SELECT_ROLE", role="police")
    alice.wait("ROLE_CONFIRMED")
    bob.send("SELECT_ROLE", role="thief")
    bob.wait("ROLE_CONFIRMED")
    bob.wait("GAME_START")
    alice.wait("GAME_START")

    bob.close()
    notice = alice.wait("PLAYER_DISCONNECTED")
    assert notice["player_id"] == "P2"
    assert notice["started"] is True
    assert server.session.abandoned
    assert not server.session.started


def test_network_manager_joins_discovered_host() -> None:
    host = NetworkManager()
    guest = NetworkManager()
    try:
        host_address = host.host(seed=4)
        discovered_address = guest.join_discovered(timeout=1.5)
        assert discovered_address is not None
        assert discovered_address[1] == host_address[1]
        assert guest.connected
    finally:
        guest.close()
        host.close()


def test_join_search_can_be_cancelled_without_leaking_a_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    host = NetworkManager()
    pygame.font.init()
    app = SimpleNamespace(
        settings=GameSettings(),
        fonts=Fonts(),
        go_to=lambda _factory: None,
    )
    screen = NetworkSetup(app)
    connected = threading.Event()
    try:
        host_address = host.host(seed=4)

        def delayed_join(
            network: NetworkManager,
            timeout: float = 4.0,
            cancelled: threading.Event | None = None,
        ) -> tuple[str, int]:
            network.join("127.0.0.1", host_address[1])
            connected.set()
            assert cancelled is not None
            cancelled.wait(2.0)
            return "127.0.0.1", host_address[1]

        monkeypatch.setattr(NetworkManager, "join_discovered", delayed_join)
        screen._join()
        assert connected.wait(2.0)
        screen._back()
        assert screen._join_thread is not None
        screen._join_thread.join(timeout=2.0)
        assert not screen._join_thread.is_alive()

        deadline = time.monotonic() + 2.0
        while host._server is not None and host._server.player_count > 1:
            if time.monotonic() >= deadline:
                break
            time.sleep(0.01)
        assert host._server is not None
        assert host._server.player_count == 1
    finally:
        if screen.phase == "lobby":
            screen._leave_lobby()
        host.close()


def test_discovery_skips_full_server() -> None:
    host = NetworkManager()
    guest = NetworkManager()
    third = NetworkManager()
    try:
        host.host(seed=4)
        assert guest.join_discovered(timeout=1.5) is not None
        assert third.join_discovered(timeout=1.0) is None
        assert not third.connected
    finally:
        third.close()
        guest.close()
        host.close()


def test_host_survives_discovery_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    def unavailable(_port: int, status=None) -> None:
        raise OSError("port 50506 occupé")

    monkeypatch.setattr("multiplayer.network_manager.ServerDiscovery", unavailable)
    host = NetworkManager()
    try:
        address = host.host(seed=4)
        assert address[1] > 0
        assert host.connected
        assert host.local_address.endswith(f":{address[1]}")
        assert "découverte" in host.discovery_error.lower()
    finally:
        host.close()


def test_split_address_validates_manual_endpoint() -> None:
    assert split_address("192.168.1.20:50505") == ("192.168.1.20", 50505)
    assert split_address(" localhost:6000 ") == ("localhost", 6000)
    with pytest.raises(ValueError):
        split_address("")
    with pytest.raises(ValueError):
        split_address("192.168.1.20")
    with pytest.raises(ValueError):
        split_address("192.168.1.20:abc")
    with pytest.raises(ValueError):
        split_address("192.168.1.20:70000")


def test_network_setup_connects_with_a_direct_address() -> None:
    host = NetworkManager()
    pygame.font.init()
    app = SimpleNamespace(
        settings=GameSettings(),
        fonts=Fonts(),
        go_to=lambda _factory: None,
    )
    screen = NetworkSetup(app)
    try:
        port = host.host(seed=4)[1]
        screen.address_input.value = f"127.0.0.1:{port}"
        screen._connect_direct()
        deadline = time.monotonic() + 3.0
        while screen.phase == "searching" and time.monotonic() < deadline:
            screen.update(0.02)
            time.sleep(0.01)
        assert screen.phase == "lobby", screen.error
        assert screen.network.connected
    finally:
        if screen.phase == "lobby":
            screen._leave_lobby()
        else:
            screen.network.close()
        host.close()


def test_multiplayer_choice_screen_has_host_and_join_buttons() -> None:
    pygame.font.init()
    app = SimpleNamespace(
        settings=GameSettings(),
        fonts=Fonts(),
        go_to=lambda _factory: None,
    )
    screen = NetworkSetup(app)
    try:
        assert (screen.host_button.label, screen.join_button.label) == (
            "Héberger",
            "Rejoindre",
        )
        assert not any(
            hasattr(screen, name) for name in ("host_port", "join_ip", "join_port")
        )
        assert not screen.host_button.rect.colliderect(screen.join_button.rect)
        screen.draw(pygame.Surface(WINDOW_SIZE))
    finally:
        screen.network.close()


def test_server_refuses_rematch_while_running(live_server) -> None:
    server, _port, make_client = live_server
    alice = make_client()
    bob = make_client()
    alice.send("SELECT_ROLE", role="police")
    alice.wait("ROLE_CONFIRMED")
    bob.send("SELECT_ROLE", role="thief")
    bob.wait("ROLE_CONFIRMED")
    bob.wait("GAME_START")
    alice.wait("GAME_START")
    alice.send("CREATE_GAME")
    error = alice.wait("ERROR")
    assert error["code"] == "game_running"
    assert server.session.manager is not None
