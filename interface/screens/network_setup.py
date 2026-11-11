"""Écran Multijoueur : héberger, découvrir ou connecter un hôte, puis salon des camps."""

from __future__ import annotations

import queue
import random
import threading

import pygame

from config import GameSettings
from core.constants import Team
from core.game_manager import GameConfig
from core.graph import build_default_graph
from interface import theme
from interface.app import App, Scene
from interface.components.controls import Button, TextInput, pill
from interface.theme import text
from modes.multiplayer import settings_to_rules
from multiplayer.client import NetworkError
from multiplayer.network_manager import NetworkManager


def split_address(value: str) -> tuple[str, int]:
    """Analyse « ip:port » ou « hôte:port » saisi par l'utilisateur."""
    address = value.strip()
    if not address:
        raise ValueError("Indiquez une adresse IP et un port.")
    if ":" not in address:
        raise ValueError("Format attendu : IP:port (exemple 192.168.1.20:50505).")
    host, port_text = address.rsplit(":", 1)
    host = host.strip()
    if not host or " " in host:
        raise ValueError("Adresse IP invalide.")
    try:
        port = int(port_text.strip())
    except ValueError as exc:
        raise ValueError("Port invalide : utilisez un nombre entre 1 et 65535.") from exc
    if not 0 < port < 65536:
        raise ValueError("Port invalide : utilisez un nombre entre 1 et 65535.")
    return host, port


class NetworkSetup(Scene):
    def __init__(self, app: App) -> None:
        self.app = app
        self.graph = build_default_graph()
        self.settings: GameSettings = app.settings
        self.network = NetworkManager()
        self.phase = "choice"
        self.mode = ""
        self.error = ""
        self.notice = ""
        self._handed_off = False
        self._join_cancel = threading.Event()
        self._join_result_lock = threading.Lock()
        self._join_generation = 0
        self._search_elapsed = 0.0
        self._search_label = ""
        self._search_mode = "discover"
        self._join_thread: threading.Thread | None = None
        self._join_results: queue.Queue[
            tuple[int, NetworkManager | None, str | None]
        ] = queue.Queue()

        self.host_button = Button(
            rect=pygame.Rect(210, 414, 320, 54),
            label="Héberger",
            primary=True,
            on_click=self._host,
        )
        self.join_button = Button(
            rect=pygame.Rect(750, 414, 320, 54),
            label="Rejoindre",
            primary=True,
            on_click=self._join,
        )
        self.back_button = Button(
            rect=pygame.Rect(120, 700, 190, 46),
            label="Retour",
            on_click=self._back,
        )
        self.address_input = TextInput(
            rect=pygame.Rect(120, 580, 360, 44),
            placeholder="192.168.1.20:50505",
            max_length=64,
            on_submit=self._submit_address,
        )
        self.connect_button = Button(
            rect=pygame.Rect(492, 580, 200, 46),
            label="Se connecter",
            on_click=self._connect_direct,
        )
        self.role_thief = Button(
            rect=pygame.Rect(396, 392, 220, 48),
            label="Prendre VOLEUR",
            on_click=lambda: self._select_role(Team.THIEF),
        )
        self.role_police = Button(
            rect=pygame.Rect(664, 392, 220, 48),
            label="Prendre POLICE",
            on_click=lambda: self._select_role(Team.POLICE),
        )

    # ------------------------------------------------------------------ actions

    def _game_config(self) -> GameConfig:
        return GameConfig(
            max_moves=self.settings.max_moves,
            repetition_limit=self.settings.repetition_limit,
            rules=settings_to_rules(self.settings),
        )

    def _host(self) -> None:
        self.error = ""
        self.notice = ""
        seed = random.randrange(100_000)
        try:
            self.network.host(seed=seed, config=self._game_config())
        except NetworkError as exc:
            self.error = str(exc)
            return
        self.mode = "host"
        self.phase = "lobby"

    def _join(self) -> None:
        self.error = ""
        self.notice = "Recherche d'un hôte sur le réseau local…"
        self._search_label = "Recherche d'un hôte sur le réseau local…"
        self._search_mode = "discover"
        self._begin_search(None)

    def _connect_direct(self) -> None:
        self._submit_address(self.address_input.value)

    def _submit_address(self, value: str) -> None:
        self.error = ""
        self.notice = ""
        try:
            target = split_address(value)
        except ValueError as exc:
            self.error = str(exc)
            return
        self.address_input.focused = False
        self._search_label = f"Connexion à {target[0]}:{target[1]}…"
        self.notice = self._search_label
        self._search_mode = "direct"
        self._begin_search(target)

    def _begin_search(self, target: tuple[str, int] | None) -> None:
        self.phase = "searching"
        self._search_elapsed = 0.0
        self._join_cancel.clear()
        self._join_generation += 1
        generation = self._join_generation
        self._join_thread = threading.Thread(
            target=self._connect_worker,
            args=(generation, target),
            name="police-join-discovery",
            daemon=True,
        )
        self._join_thread.start()

    def _connect_worker(
        self, generation: int, target: tuple[str, int] | None
    ) -> None:
        network = NetworkManager()
        try:
            if target is None:
                address = network.join_discovered(cancelled=self._join_cancel)
                if address is None:
                    raise NetworkError(
                        "Aucun hôte joignable trouvé. Vérifiez le réseau local et le "
                        "pare-feu Windows, réessayez, ou utilisez la connexion directe "
                        "(IP:port affichée dans le salon de l'hôte)."
                    )
            else:
                network.join(*target)
            if self._join_cancel.is_set():
                network.close()
                return
        except (NetworkError, OSError) as exc:
            network.close()
            with self._join_result_lock:
                if not self._join_cancel.is_set():
                    self._join_results.put((generation, None, str(exc)))
        else:
            with self._join_result_lock:
                if self._join_cancel.is_set():
                    network.close()
                else:
                    self._join_results.put((generation, network, None))

    def _select_role(self, role: Team) -> None:
        if self.phase != "lobby" or not self.network.connected:
            return
        self.error = ""
        if self.network.send("SELECT_ROLE", role=role.value):
            self.notice = "Choix envoyé au serveur…"
        else:
            self.error = "Connexion perdue."

    def _leave_lobby(self) -> None:
        if self._handed_off:
            return
        self.network.close()
        self.phase = "choice"
        self.mode = ""
        self.error = ""
        self.notice = ""

    def _back(self) -> None:
        self.address_input.focused = False
        if self.phase == "lobby":
            self._leave_lobby()
            return
        if self.phase == "searching":
            with self._join_result_lock:
                self._join_cancel.set()
                self._join_generation += 1
                while True:
                    try:
                        result = self._join_results.get_nowait()
                    except queue.Empty:
                        break
                    network = result[1]
                    if network is not None:
                        network.close()
        from interface.screens.menu import MainMenu

        self.network.close()
        self.app.go_to(lambda: MainMenu(self.app))

    def _start_game(self, message: dict) -> None:
        from interface.screens.game import GameScreen
        from modes.multiplayer import NetworkController

        try:
            controller = NetworkController(
                self.graph, self.settings, self.network, message
            )
        except (KeyError, TypeError, ValueError) as exc:
            self.error = f"État de partie invalide reçu du serveur : {exc}"
            return
        self._handed_off = True
        self.app.go_to(lambda: GameScreen(self.app, controller))

    # ------------------------------------------------------------------ messages

    def _poll(self) -> None:
        if self._handed_off:
            return
        while True:
            try:
                generation, network, error = self._join_results.get_nowait()
            except queue.Empty:
                break
            if generation != self._join_generation or self.phase != "searching":
                if network is not None:
                    network.close()
                continue
            if error is not None:
                self.error = error
                self.notice = ""
                self.phase = "choice"
            else:
                if network is None:
                    self.error = "La connexion au serveur n'a pas pu être établie."
                    self.phase = "choice"
                    continue
                self.network.close()
                self.network = network
                self.mode = "join"
                self.notice = ""
                self.phase = "lobby"
        for message in self.network.poll():
            kind = message.get("type")
            if kind == "GAME_START":
                self._start_game(message)
                return
            if kind == "ROLE_CONFIRMED":
                self.notice = "Camp confirmé."
            elif kind == "ERROR":
                self.error = str(message.get("message", "Erreur réseau."))
                self.notice = ""
            elif kind == "DISCONNECTED":
                if not self._handed_off:
                    self.error = str(message.get("reason", "Connexion perdue."))
                    self.phase = "choice"
                    self.mode = ""

    def _refresh_buttons(self) -> None:
        lobby = self.phase == "lobby" and self.network.connected and not self.network.started
        role = self.network.role
        available = set(self.network.available_roles)
        self.role_thief.enabled = lobby and (role is Team.THIEF or Team.THIEF in available)
        self.role_police.enabled = lobby and (role is Team.POLICE or Team.POLICE in available)
        self.role_thief.label = "VOLEUR (vous)" if role is Team.THIEF else "Prendre VOLEUR"
        self.role_police.label = "POLICE (vous)" if role is Team.POLICE else "Prendre POLICE"

    # ------------------------------------------------------------------ scène

    def handle(self, event: pygame.event.Event) -> None:
        if self.phase == "choice":
            for control in (
                self.address_input,
                self.connect_button,
                self.host_button,
                self.join_button,
                self.back_button,
            ):
                control.handle(event)
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                self._back()
        elif self.phase == "searching":
            self.back_button.handle(event)
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                self._back()
        else:
            for control in (self.role_thief, self.role_police, self.back_button):
                control.handle(event)
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                self._leave_lobby()
            elif event.type == pygame.KEYDOWN and event.key in (pygame.K_1, pygame.K_2):
                if event.key == pygame.K_1:
                    self._select_role(Team.THIEF)
                else:
                    self._select_role(Team.POLICE)

    def update(self, dt: float) -> None:
        self._poll()
        if self.phase == "searching":
            self._search_elapsed += dt
        self._refresh_buttons()
        for control in (
            self.host_button,
            self.join_button,
            self.connect_button,
            self.address_input,
            self.back_button,
            self.role_thief,
            self.role_police,
        ):
            if hasattr(control, "update"):
                control.update(dt)

    # ------------------------------------------------------------------ dessin

    def draw(self, surface: pygame.Surface) -> None:
        surface.fill(theme.BG)
        self._draw_backdrop(surface)
        fonts = self.app.fonts
        theme.tracking_text(
            surface, fonts.ui(12, bold=True), "RÉSEAU LOCAL", (120, 74), theme.TEXT_DIM, 3
        )
        text(surface, fonts.title(46), "Multijoueur", (118, 96), theme.TEXT)
        text(
            surface,
            fonts.ui(16),
            "Deux ordinateurs sur le même réseau Wi-Fi : un hôte, un invité, un serveur autoritaire.",
            (120, 168),
            theme.TEXT_MUTED,
        )
        if self.phase == "choice":
            self._draw_choice(surface)
        elif self.phase == "searching":
            self._draw_searching(surface)
        else:
            self._draw_lobby(surface)
        self.back_button.draw(surface, fonts)

    def _draw_backdrop(self, surface: pygame.Surface) -> None:
        layer = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
        for index in range(0, 900, 64):
            alpha = max(0, 20 - index // 48)
            pygame.draw.line(
                layer,
                (*theme.BOARD_GLOW, alpha),
                (0, 140 + index),
                (surface.get_width(), 140 + index),
                1,
            )
        surface.blit(layer, (0, 0))

    def _draw_choice(self, surface: pygame.Surface) -> None:
        fonts = self.app.fonts
        left = pygame.Rect(120, 238, 500, 300)
        right = pygame.Rect(660, 238, 500, 300)
        theme.panel(surface, left, fill=theme.BG_SOFT)
        theme.panel(surface, right, fill=theme.BG_SOFT)

        theme.tracking_text(
            surface, fonts.ui(12, bold=True), "HÉBERGER UNE PARTIE", (146, 262), theme.TEXT_DIM, 2
        )
        text(surface, fonts.ui(14), "Créez une partie sur cet ordinateur.", (146, 310), theme.TEXT_MUTED)
        text(surface, fonts.ui(14), "L'hôte sera détecté automatiquement sur le réseau local.", (146, 334), theme.TEXT_MUTED)
        self.host_button.draw(surface, fonts)

        theme.tracking_text(
            surface, fonts.ui(12, bold=True), "REJOINDRE UNE PARTIE", (686, 262), theme.TEXT_DIM, 2
        )
        text(
            surface,
            fonts.ui(14),
            "Recherchez automatiquement un hôte sur le réseau local.",
            (686, 310),
            theme.TEXT_MUTED,
        )
        self.join_button.draw(surface, fonts)

        theme.tracking_text(
            surface,
            fonts.ui(12, bold=True),
            "CONNEXION DIRECTE (IP:PORT)",
            (120, 556),
            theme.TEXT_DIM,
            2,
        )
        text(
            surface,
            fonts.ui(13),
            "Si la découverte UDP est bloquée : l'adresse est affichée chez l'hôte.",
            (712, 568),
            theme.TEXT_DIM,
        )
        self.address_input.draw(surface, fonts)
        self.connect_button.draw(surface, fonts)

        self._draw_feedback(surface, (120, 648))

    def _draw_searching(self, surface: pygame.Surface) -> None:
        fonts = self.app.fonts
        card = pygame.Rect(300, 238, 680, 300)
        theme.panel(surface, card, fill=theme.BG_SOFT, stroke=theme.STROKE_SOFT, radius=22)
        text(surface, fonts.ui(24, bold=True), "Recherche d'une partie", (card.left + 30, card.top + 34), theme.TEXT)
        text(
            surface,
            fonts.ui(15),
            self._search_label or "Recherche d'un hôte sur le réseau local…",
            (card.left + 30, card.top + 94),
            theme.TEXT_MUTED,
        )
        dots = "." * (1 + int(self._search_elapsed * 3) % 3)
        busy = "Connexion" if self._search_mode == "direct" else "Recherche"
        text(
            surface,
            fonts.mono(14),
            f"{busy} en cours{dots}",
            (card.left + 30, card.top + 132),
            theme.POLICE,
        )
        text(
            surface,
            fonts.ui(13),
            "La recherche peut être annulée avec Retour ou Échap.",
            (card.left + 30, card.top + 170),
            theme.TEXT_DIM,
        )

    def _draw_feedback(self, surface: pygame.Surface, pos: tuple[int, int]) -> None:
        fonts = self.app.fonts
        if self.error:
            font, value, color = fonts.ui(14), self.error, theme.THIEF
        elif self.notice:
            font, value, color = fonts.ui(14), self.notice, theme.WARNING
        else:
            font = fonts.mono(12)
            value = "Le serveur vérifie chaque coup : aucun client ne fixe l'état officiel."
            color = theme.TEXT_DIM
        self._draw_wrapped(
            surface, font, value, pos, color, surface.get_width() - pos[0] - 24
        )

    def _draw_wrapped(
        self,
        surface: pygame.Surface,
        font: pygame.font.Font,
        value: str,
        pos: tuple[int, int],
        color: tuple[int, int, int],
        max_width: int,
    ) -> None:
        lines: list[str] = []
        current = ""
        for word in value.split():
            candidate = f"{current} {word}".strip()
            if current and font.size(candidate)[0] > max_width:
                lines.append(current)
                current = word
            else:
                current = candidate
        if current:
            lines.append(current)
        for index, line in enumerate(lines):
            text(surface, font, line, (pos[0], pos[1] + index * (font.get_linesize() + 2)), color)

    def _draw_lobby(self, surface: pygame.Surface) -> None:
        fonts = self.app.fonts
        card = pygame.Rect(300, 186, 680, 430)
        theme.panel(surface, card, fill=theme.BG_SOFT, stroke=theme.STROKE_SOFT, radius=22)
        text(surface, fonts.ui(24, bold=True), "Salon", (330, 208), theme.TEXT)
        connected = self.network.connected and self.network.state == "connected"
        pill(
            surface,
            fonts,
            "CONNECTÉ" if connected else "HORS LIGNE",
            (card.right - 90, 222),
            theme.SUCCESS if connected else theme.THIEF,
        )

        me = next(
            (player for player in self.network.players if player.get("player_id") == self.network.player_id),
            None,
        )
        other = next(
            (player for player in self.network.players if player.get("player_id") != self.network.player_id),
            None,
        )
        role_text = f"Connecté en tant que {self.network.player_id or '—'}"
        text(surface, fonts.mono(12), role_text, (330, 250), theme.TEXT_MUTED)

        endpoint = self.network.local_address
        if not endpoint and self.network.join_address is not None:
            endpoint = f"{self.network.join_address[0]}:{self.network.join_address[1]}"
        if endpoint:
            text(
                surface,
                fonts.mono(12),
                f"Adresse : {endpoint}",
                (330, 272),
                theme.TEXT_MUTED,
            )

        self._draw_slot(surface, pygame.Rect(330, 308, 300, 72), "VOUS", me, theme.POLICE)
        self._draw_slot(surface, pygame.Rect(650, 308, 300, 72), "ADVERSAIRE", other, theme.THIEF)

        self.role_thief.draw(surface, fonts)
        self.role_police.draw(surface, fonts)

        if not connected:
            status = "Connexion interrompue."
            color = theme.THIEF
        elif len(self.network.players) < 2:
            status = "En attente d'un second joueur…"
            color = theme.WARNING
        elif self.network.role is None:
            status = "Choisissez votre camp pour lancer la partie."
            color = theme.TEXT_MUTED
        elif other is not None and other.get("role") is None:
            status = "L'autre joueur choisit son camp…"
            color = theme.TEXT_MUTED
        else:
            status = "Les deux camps sont prêts : lancement…"
            color = theme.SUCCESS
        text(surface, fonts.ui(15), status, (330, 456), color)

        feedback_width = card.right - 330 - 24
        if self.error:
            self._draw_wrapped(
                surface, fonts.ui(14), self.error, (330, 486), theme.THIEF, feedback_width
            )
        elif self.notice:
            self._draw_wrapped(
                surface, fonts.ui(13), self.notice, (330, 486), theme.TEXT_DIM, feedback_width
            )
        elif self.network.discovery_error and self.network.is_host:
            self._draw_wrapped(
                surface,
                fonts.ui(13),
                self.network.discovery_error,
                (330, 486),
                theme.WARNING,
                feedback_width,
            )
        else:
            text(
                surface,
                fonts.mono(12),
                "Les rôles identiques sont refusés par le serveur.",
                (330, 488),
                theme.TEXT_DIM,
            )
        text(
            surface,
            fonts.mono(11),
            "Échap : quitter le salon · 1/2 : choisir un camp",
            (330, 528),
            theme.TEXT_DIM,
        )

    def _draw_slot(
        self,
        surface: pygame.Surface,
        rect: pygame.Rect,
        label: str,
        player: dict | None,
        accent: tuple[int, int, int],
    ) -> None:
        fonts = self.app.fonts
        theme.panel(surface, rect, fill=theme.PANEL, radius=12)
        theme.tracking_text(
            surface, fonts.ui(10, bold=True), label, (rect.left + 16, rect.top + 12), theme.TEXT_DIM, 2
        )
        if player is None:
            text(surface, fonts.ui(14), "en attente…", (rect.left + 16, rect.top + 36), theme.TEXT_DIM)
            return
        name = str(player.get("name") or player.get("player_id") or "?")
        role = player.get("role")
        text(surface, fonts.ui(15, bold=True), name, (rect.left + 16, rect.top + 32), theme.TEXT)
        if role:
            role_text = "POLICE" if role == "police" else "VOLEUR"
            color = theme.POLICE if role == "police" else theme.THIEF
            text(surface, fonts.mono(12, bold=True), role_text, (rect.right - 16, rect.top + 34), color, right=True)
        else:
            text(surface, fonts.mono(11), "camp non choisi", (rect.right - 16, rect.top + 34), theme.TEXT_DIM, right=True)
