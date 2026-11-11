"""Écran de partie : plateau interactif, HUD, panneau IA et arbre Minimax.

L'écran ne contient aucune règle : il observe un `MatchController` (démo ou solo)
et lui transmet les intentions du joueur. Le rendu est purement présentationnel.
"""

from __future__ import annotations

import pygame

from config import BOARD_IMAGE
from core.constants import CENTER, GameStatus, Team
from interface import theme
from interface.animations import clamp
from interface.app import App, Scene
from interface.board import BoardRenderer
from interface.components.controls import Button, pill, section_title, thinking_dots
from interface.theme import text
from modes.match_controller import MatchController

BOARD_AREA = pygame.Rect(30, 30, 712, 740)
PANEL_AREA = pygame.Rect(766, 30, 484, 740)

PANEL_X = 794
PANEL_W = 424
PANEL_RIGHT = PANEL_X + PANEL_W


class GameScreen(Scene):
    def __init__(self, app: App, controller: MatchController) -> None:
        self.app = app
        self.controller = controller
        self.clock = 0.0
        self.entry = 0.0
        self.hover: str | None = None
        self.show_tree = False
        self.show_debug = False
        self.show_reference = False
        self.board = BoardRenderer(
            controller.graph, BOARD_AREA, app.fonts, image_path=BOARD_IMAGE
        )
        self.buttons = self._build_buttons()
        self.overlay_buttons = [
            Button(
                rect=pygame.Rect(136, 470, 230, 48),
                label="Rejouer",
                primary=True,
                on_click=self._restart,
            ),
            Button(
                rect=pygame.Rect(406, 470, 230, 48),
                label="Menu",
                on_click=self._menu,
            ),
        ]

    # ------------------------------------------------------------------ contrôles

    def _build_buttons(self) -> list[Button]:
        kind = self.controller.kind
        if kind == "demo":
            return [
                Button(
                    rect=pygame.Rect(794, 622, 138, 32),
                    label="Pause",
                    on_click=self._toggle_pause,
                ),
                Button(
                    rect=pygame.Rect(940, 622, 138, 32),
                    label="Pas à pas",
                    on_click=self._step,
                ),
                Button(
                    rect=pygame.Rect(1086, 622, 140, 32),
                    label=self._speed_label(),
                    on_click=self._cycle_speed,
                ),
                Button(
                    rect=pygame.Rect(794, 662, 210, 34),
                    label="Recommencer",
                    on_click=self._restart,
                ),
                Button(
                    rect=pygame.Rect(1016, 662, 210, 34),
                    label="Menu",
                    on_click=self._menu,
                ),
                Button(
                    rect=pygame.Rect(794, 704, 138, 32),
                    label="Arbre",
                    on_click=self._toggle_tree,
                ),
                Button(
                    rect=pygame.Rect(940, 704, 138, 32),
                    label="Débug",
                    on_click=self._toggle_debug,
                ),
                Button(
                    rect=pygame.Rect(1086, 704, 140, 32),
                    label="Réf.",
                    on_click=self._toggle_reference,
                ),
            ]
        restart_label = "Rejouer" if kind == "network" else "Recommencer"
        return [
            Button(
                rect=pygame.Rect(794, 630, 210, 42),
                label=restart_label,
                on_click=self._restart,
            ),
            Button(
                rect=pygame.Rect(1016, 630, 210, 42),
                label="Menu",
                on_click=self._menu,
            ),
            Button(
                rect=pygame.Rect(794, 684, 138, 34),
                label="Arbre",
                on_click=self._toggle_tree,
            ),
            Button(
                rect=pygame.Rect(940, 684, 138, 34),
                label="Débug",
                on_click=self._toggle_debug,
            ),
            Button(
                rect=pygame.Rect(1086, 684, 140, 34),
                label="Réf.",
                on_click=self._toggle_reference,
            ),
        ]

    def _speed_label(self) -> str:
        return f"Vitesse ×{self.controller.speed:g}"

    def _toggle_pause(self) -> None:
        self.controller.toggle_pause()
        button = self.buttons[0]
        button.label = "Pause" if not self.controller.paused else "Lecture"

    def _step(self) -> None:
        if not self.controller.paused:
            self.controller.set_paused(True)
            self.buttons[0].label = "Lecture"
        self.controller.step_once()

    def _cycle_speed(self) -> None:
        steps = (0.5, 1.0, 1.5, 2.0, 3.0, 4.0)
        current = self.controller.speed
        nxt = next((value for value in steps if value > current + 1e-6), steps[0])
        self.controller.speed = nxt
        self.buttons[2].label = self._speed_label()

    def _toggle_tree(self) -> None:
        self.show_tree = not self.show_tree

    def _toggle_debug(self) -> None:
        self.show_debug = not self.show_debug

    def _toggle_reference(self) -> None:
        self.show_reference = not self.show_reference

    def _restart(self) -> None:
        self.controller.restart()
        self.board.clear_animation()
        self.hover = None
        self.show_tree = False
        if self.controller.kind == "demo":
            self.buttons[0].label = "Pause"
            self.buttons[2].label = self._speed_label()

    def _menu(self) -> None:
        self.controller.close()
        from interface.screens.menu import MainMenu

        self.app.go_to(lambda: MainMenu(self.app))

    # ------------------------------------------------------------------ scène

    def handle(self, event: pygame.event.Event) -> None:
        if self.controller.is_over:
            for button in self.overlay_buttons:
                button.handle(event)
        elif self.show_tree:
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                self.show_tree = False
        else:
            for button in self.buttons:
                button.handle(event)
            if event.type == pygame.MOUSEMOTION:
                self.hover = self._vertex_at(event.pos)
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                vertex = self._vertex_at(event.pos)
                if vertex is not None:
                    self.controller.handle_board_click(vertex)

        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                if self.show_tree:
                    self.show_tree = False
                else:
                    self._menu()
            elif event.key == pygame.K_t:
                self.show_tree = not self.show_tree
            elif event.key == pygame.K_d:
                self.show_debug = not self.show_debug
            elif event.key == pygame.K_v:
                self.show_reference = not self.show_reference
            elif event.key == pygame.K_r:
                self._restart()
            elif event.key in (pygame.K_SPACE, pygame.K_n) and self.controller.kind == "demo":
                if event.key == pygame.K_SPACE:
                    self._toggle_pause()
                else:
                    self._step()

    def _vertex_at(self, pos: tuple[int, int]) -> str | None:
        local = (pos[0] - BOARD_AREA.x, pos[1] - BOARD_AREA.y)
        return self.board.vertex_at(local, radius=18.0)

    def update(self, dt: float) -> None:
        self.clock += dt
        self.entry = min(1.0, self.entry + dt * 4.0)
        self.controller.update(dt)
        move = self.controller.take_animation()
        if move is not None:
            speed = getattr(self.controller, "speed", 1.0)
            duration = max(0.06, 0.17 / max(0.6, speed))
            self.board.begin_move(move, duration=duration)
        self.board.update(dt)
        for button in (*self.buttons, *self.overlay_buttons):
            button.update(dt)
        if self.controller.kind == "demo":
            self.buttons[0].label = "Pause" if not self.controller.paused else "Lecture"
        if self.controller.kind == "network":
            self.overlay_buttons[0].enabled = not getattr(self.controller, "abandoned", False)

    # ------------------------------------------------------------------ dessin

    def draw(self, surface: pygame.Surface) -> None:
        surface.fill(theme.BG)
        theme.panel(surface, BOARD_AREA, fill=theme.BG_SOFT, stroke=theme.STROKE_SOFT, radius=22)
        self.board.draw(
            surface,
            self.controller.state,
            legal_targets=self.controller.legal_targets(),
            selected_vertex=self.controller.selected_vertex,
            hover_vertex=self.hover,
            preview=self.controller.preview,
            thinking=self.controller.thinking,
            cooldown_ratio=self.controller.cooldown_ratio,
            show_debug=self.show_debug,
            show_reference=self.show_reference,
        )
        self._draw_panel(surface)
        if self.show_tree:
            self._draw_tree(surface)
        if self.controller.is_over:
            self._draw_result(surface)

    # ------------------------------------------------------------------ panneau

    def _draw_panel(self, surface: pygame.Surface) -> None:
        fonts = self.app.fonts
        controller = self.controller
        surface_rect = PANEL_AREA
        theme.panel(surface, surface_rect, fill=theme.BG_SOFT, stroke=theme.STROKE_SOFT, radius=22)

        theme.tracking_text(
            surface, fonts.ui(11, bold=True), "MODE", (PANEL_X, 52), theme.TEXT_DIM, 2
        )
        text(
            surface,
            fonts.ui(22, bold=True),
            controller.mode_name.upper(),
            (PANEL_X, 66),
            theme.TEXT,
        )
        if controller.kind in {"solo", "network"} and controller.human_team is not None:
            role = "VOLEUR" if controller.human_team is Team.THIEF else "POLICE"
            label = f"vous : {role}"
            if controller.kind == "network":
                label = f"{label} · {controller.opponent_label()}"
            self._draw_fitted_text(
                surface,
                fonts.mono(12),
                label,
                (PANEL_X, 98),
                theme.TEXT_MUTED,
                PANEL_W,
            )
        self._draw_status_pill(surface)

        self._draw_turn_card(surface)
        self._draw_positions_card(surface)
        if controller.kind == "network":
            self._draw_network_card(surface)
            self._draw_journal_card(surface)
        else:
            self._draw_ai_card(surface)
            self._draw_root_card(surface)
        for button in self.buttons:
            button.draw(surface, fonts)
        hints = {
            "demo": "Espace pause · N pas · T arbre · D debug · Échap menu",
            "network": "T arbre · D debug · V référence · Échap quitter la partie",
        }
        hint = hints.get(controller.kind, "T arbre · D debug · V référence · Échap menu")
        text(surface, fonts.mono(11), hint, (PANEL_X, 744), theme.TEXT_DIM)

    def _draw_status_pill(self, surface: pygame.Surface) -> None:
        mapping = {
            GameStatus.ONGOING: ("EN COURS", theme.SUCCESS),
            GameStatus.POLICE_WIN: ("VICTOIRE POLICE", theme.POLICE),
            GameStatus.THIEF_WIN: ("VICTOIRE VOLEUR", theme.THIEF),
            GameStatus.DRAW: ("MATCH NUL", theme.DRAW),
        }
        label, color = mapping[self.controller.status]
        if getattr(self.controller, "abandoned", False):
            label, color = "CONNEXION PERDUE", theme.WARNING
        width = self.app.fonts.ui(13, bold=True).size(label)[0] + 28
        center = (PANEL_RIGHT - width // 2, 82)
        pill(surface, self.app.fonts, label, center, color)

    def _draw_turn_card(self, surface: pygame.Surface) -> None:
        fonts = self.app.fonts
        controller = self.controller
        card = pygame.Rect(778, 114, 460, 108)
        theme.panel(surface, card, fill=theme.PANEL, radius=14)

        theme.tracking_text(
            surface, fonts.ui(11, bold=True), "TOUR", (PANEL_X, 126), theme.TEXT_DIM, 2
        )
        text(
            surface,
            fonts.mono(12),
            f"coup {controller.ply // 2 + 1} · demi-coup {controller.ply}",
            (PANEL_RIGHT, 126),
            theme.TEXT_DIM,
            right=True,
        )
        if controller.ply > 0 and controller.manager.move_history:
            last = controller.manager.move_history[-1]
            text(
                surface,
                fonts.mono(11),
                f"dernier : {self._move_label(last)}",
                (PANEL_RIGHT, 146),
                theme.TEXT_DIM,
                right=True,
            )

        turn = controller.state.turn
        color = theme.POLICE if turn is Team.POLICE else theme.THIEF
        name = "POLICE" if turn is Team.POLICE else "VOLEUR"
        text(surface, fonts.ui(24, bold=True), name, (PANEL_X, 142), color)
        if controller.thinking is not None:
            thinking_dots(surface, PANEL_X + 118, 154, self.clock * 2.2)
            text(surface, fonts.ui(12), "réflexion", (PANEL_X + 158, 146), theme.TEXT_MUTED)
        elif controller.can_human_play:
            pill(surface, fonts, "à vous", (PANEL_X + 182, 154), theme.SUCCESS)

        ratio = controller.cooldown_ratio
        if ratio is None:
            label, bar_ratio, bar_color = "Retour au centre libre", 1.0, theme.SUCCESS
        elif ratio >= 1:
            label, bar_ratio, bar_color = "Centre ouvert au voleur", 1.0, theme.SUCCESS
        else:
            remaining = max(0, controller.rules.return_cooldown - controller.ply)
            label, bar_ratio, bar_color = (
                f"Cooldown centre · {remaining} demi-coup(s)",
                ratio,
                theme.WARNING,
            )
        text(surface, fonts.ui(12), label, (PANEL_X, 178), theme.TEXT_MUTED)
        track = pygame.Rect(PANEL_X, 198, PANEL_W, 6)
        pygame.draw.rect(surface, theme.STROKE_SOFT, track, border_radius=3)
        filled = pygame.Rect(track.left, track.top, round(track.width * clamp(bar_ratio)), 6)
        pygame.draw.rect(surface, bar_color, filled, border_radius=3)

    def _draw_positions_card(self, surface: pygame.Surface) -> None:
        fonts = self.app.fonts
        state = self.controller.state
        card = pygame.Rect(778, 230, 460, 100)
        theme.panel(surface, card, fill=theme.PANEL, radius=14)
        section_title(surface, fonts, "POSITIONS", PANEL_X, 242)

        text(surface, fonts.ui(13), "Voleur", (PANEL_X, 268), theme.TEXT_MUTED)
        text(
            surface,
            fonts.mono(15, bold=True),
            state.thief,
            (PANEL_RIGHT, 267),
            theme.THIEF,
            right=True,
        )
        text(surface, fonts.ui(13), "Policiers", (PANEL_X, 290), theme.TEXT_MUTED)
        police = " · ".join(
            f"P{index + 1} {vertex}" for index, vertex in enumerate(state.police)
        )
        text(
            surface,
            fonts.mono(13, bold=True),
            police,
            (PANEL_RIGHT, 290),
            theme.POLICE,
            right=True,
        )
        distance = self.controller.graph.bfs_distances(state.thief).get(CENTER)
        text(surface, fonts.ui(13), "Distance au centre", (PANEL_X, 312), theme.TEXT_MUTED)
        text(
            surface,
            fonts.mono(13, bold=True),
            "—" if distance is None else f"d = {distance}",
            (PANEL_RIGHT, 312),
            theme.TEXT,
            right=True,
        )

    def _draw_network_card(self, surface: pygame.Surface) -> None:
        fonts = self.app.fonts
        controller = self.controller
        network = controller.network
        card = pygame.Rect(778, 338, 460, 156)
        theme.panel(surface, card, fill=theme.PANEL, radius=14)
        section_title(surface, fonts, "RÉSEAU", PANEL_X, 350)

        if controller.abandoned or not network.connected:
            label, color = "INTERROMPU", theme.WARNING
        elif controller.pending:
            label, color = "ENVOI…", theme.WARNING
        elif not network.started:
            label, color = "EN ATTENTE", theme.TEXT_DIM
        else:
            label, color = "SYNCHRONISÉ", theme.SUCCESS
        pill(surface, fonts, label, (1122, 358), color)

        role = controller.human_team
        rows = [
            ("Votre camp", "VOLEUR" if role is Team.THIEF else "POLICE"),
            ("Adversaire", controller.opponent_label()),
            ("Dernier coup", self._move_label(controller.last_move) if controller.last_move else "—"),
            ("Demi-coup", f"{controller.ply}"),
            ("Partie", f"#{network.game_id}" if network.game_id else "—"),
            ("Serveur", "en ligne" if network.connected else "hors ligne"),
        ]
        for index, (label, value) in enumerate(rows):
            column = index % 2
            line = index // 2
            x = PANEL_X if column == 0 else 1016
            right = PANEL_X + 200 if column == 0 else PANEL_RIGHT
            y = 376 + line * 22
            label_font = fonts.ui(13)
            value_font = fonts.mono(13, bold=True)
            text(surface, label_font, label, (x, y), theme.TEXT_MUTED)
            available_width = right - x - label_font.size(label)[0] - 12
            self._draw_fitted_text(
                surface,
                value_font,
                value,
                (right, y),
                theme.TEXT,
                available_width,
                right=True,
            )

        self._draw_fitted_text(
            surface,
            fonts.ui(12),
            controller.note,
            (PANEL_X, 452),
            theme.TEXT_MUTED,
            PANEL_W,
        )
        self._draw_fitted_text(
            surface,
            fonts.mono(11),
            "Le serveur arbitre : chaque coup est validé avant application.",
            (PANEL_X, 472),
            theme.TEXT_DIM,
            PANEL_W,
        )

    def _draw_journal_card(self, surface: pygame.Surface) -> None:
        fonts = self.app.fonts
        history = self.controller.manager.move_history
        card = pygame.Rect(778, 502, 460, 110)
        theme.panel(surface, card, fill=theme.PANEL, radius=14)
        section_title(surface, fonts, "JOURNAL DES COUPS", PANEL_X, 514)
        if not history:
            text(
                surface,
                fonts.ui(13),
                "En attente du premier mouvement…",
                (PANEL_X, 546),
                theme.TEXT_DIM,
            )
            return
        entries = list(enumerate(history, start=1))[-4:]
        for row, (ply, move) in enumerate(reversed(entries)):
            y = 536 + row * 18
            color = theme.POLICE if move.team is Team.POLICE else theme.THIEF
            text(surface, fonts.mono(11), f"{ply:>3}", (PANEL_X, y), theme.TEXT_DIM)
            text(surface, fonts.mono(12, bold=True), self._move_label(move), (PANEL_X + 34, y), color)
            text(
                surface,
                fonts.mono(10),
                "POLICE" if move.team is Team.POLICE else "VOLEUR",
                (PANEL_RIGHT, y + 1),
                theme.TEXT_DIM,
                right=True,
            )

    def _draw_ai_card(self, surface: pygame.Surface) -> None:
        fonts = self.app.fonts
        result = self.controller.last_result
        card = pygame.Rect(778, 338, 460, 156)
        theme.panel(surface, card, fill=theme.PANEL, radius=14)
        section_title(surface, fonts, "RECHERCHE IA", PANEL_X, 350)

        team = self._result_team()
        if team is not None:
            color = theme.POLICE if team is Team.POLICE else theme.THIEF
            pill(surface, fonts, "POLICE" if team is Team.POLICE else "VOLEUR", (1122, 358), color)

        left_x, right_x = PANEL_X, 1016
        col_value_left = PANEL_X + 200
        col_value_right = PANEL_RIGHT
        rows = [
            ("Profondeur", self._value(result, lambda r: f"{r.depth}")),
            ("Nœuds", self._value(result, lambda r: f"{r.nodes:,}".replace(",", " "))),
            ("Coupures", self._value(result, lambda r: f"{r.cutoffs}")),
            ("TT hits", self._value(result, lambda r: f"{r.tt_hits}")),
            ("Temps", self._value(result, lambda r: f"{r.elapsed * 1000:.0f} ms")),
            (
                "Complet",
                self._value(result, lambda r: "oui" if r.completed else "non"),
            ),
        ]
        for index, (label, value) in enumerate(rows):
            column = index % 2
            line = index // 2
            x = left_x if column == 0 else right_x
            right = col_value_left if column == 0 else col_value_right
            y = 376 + line * 22
            text(surface, fonts.ui(13), label, (x, y), theme.TEXT_MUTED)
            text(surface, fonts.mono(13, bold=True), value, (right, y), theme.TEXT, right=True)

        score = 0 if result is None else result.score
        score_color = self._score_color(score)
        text(surface, fonts.ui(12), "Évaluation", (PANEL_X, 448), theme.TEXT_MUTED)
        text(
            surface,
            fonts.mono(14, bold=True),
            f"{score:+d}",
            (PANEL_RIGHT, 446),
            score_color,
            right=True,
        )
        self._score_bar(surface, pygame.Rect(PANEL_X, 468, PANEL_W, 10), score)

    def _draw_root_card(self, surface: pygame.Surface) -> None:
        fonts = self.app.fonts
        result = self.controller.last_result
        card = pygame.Rect(778, 502, 460, 110)
        theme.panel(surface, card, fill=theme.PANEL, radius=14)
        section_title(surface, fonts, "COUPS RACINE ÉVALUÉS", PANEL_X, 514)
        if result is None or not result.root_scores:
            text(
                surface,
                fonts.ui(13),
                "En attente de la première recherche…",
                (PANEL_X, 546),
                theme.TEXT_DIM,
            )
            return
        maximizing = result.tree.maximizing if result.tree is not None else True
        entries = sorted(result.root_scores, key=lambda item: item.score, reverse=maximizing)
        peak = max(1, max(abs(item.score) for item in entries))
        for index, entry in enumerate(entries[:4]):
            y = 536 + index * 18
            chosen = result.move is not None and entry.move == result.move
            if chosen:
                pygame.draw.circle(surface, theme.SUCCESS, (PANEL_X + 3, y + 7), 3)
            text(
                surface,
                fonts.mono(12, bold=chosen),
                self._move_label(entry.move),
                (PANEL_X + 14, y),
                theme.TEXT if chosen else theme.TEXT_MUTED,
            )
            track = pygame.Rect(PANEL_X + 150, y + 4, 200, 7)
            pygame.draw.rect(surface, theme.STROKE_SOFT, track, border_radius=3)
            width = round(track.width * abs(entry.score) / peak)
            if width > 0:
                pygame.draw.rect(
                    surface,
                    self._score_color(entry.score),
                    pygame.Rect(track.left, track.top, max(3, width), track.height),
                    border_radius=3,
                )
            text(
                surface,
                fonts.mono(12, bold=True),
                f"{entry.score:+d}",
                (PANEL_RIGHT, y),
                self._score_color(entry.score),
                right=True,
            )

    # ------------------------------------------------------------------ arbre

    def _draw_tree(self, surface: pygame.Surface) -> None:
        overlay = pygame.Surface(BOARD_AREA.size, pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 165))
        surface.blit(overlay, BOARD_AREA.topleft)
        card = pygame.Rect(BOARD_AREA.x + 14, BOARD_AREA.y + 14, BOARD_AREA.w - 28, BOARD_AREA.h - 28)
        theme.panel(surface, card, fill=theme.BG_SOFT, stroke=theme.STROKE, radius=18)

        fonts = self.app.fonts
        text(surface, fonts.ui(22, bold=True), "Arbre Minimax exploré", (card.left + 26, card.top + 22), theme.TEXT)
        text(
            surface,
            fonts.ui(13),
            "Nœuds réellement visités par la recherche (approfondissement itératif).",
            (card.left + 26, card.top + 54),
            theme.TEXT_MUTED,
        )
        result = self.controller.last_result
        if result is None or result.tree is None:
            text(
                surface,
                fonts.ui(16),
                "Aucune recherche enregistrée pour le moment.",
                (card.centerx, card.centery),
                theme.TEXT_DIM,
                center=True,
            )
            return

        tree = result.tree
        root_box = pygame.Rect(0, 0, 250, 56)
        root_box.center = (card.centerx, card.top + 128)
        border = theme.POLICE if tree.maximizing else theme.THIEF
        pygame.draw.rect(surface, theme.PANEL, root_box, border_radius=10)
        pygame.draw.rect(surface, border, root_box, width=2, border_radius=10)
        text(surface, fonts.mono(11), "RACINE", (root_box.centerx, root_box.top + 8), theme.TEXT_DIM, center=True)
        text(
            surface,
            fonts.mono(13, bold=True),
            f"{tree.score:+d}",
            (root_box.centerx, root_box.top + 24),
            self._score_color(tree.score),
            center=True,
        )
        text(surface, fonts.ui(11), "dernier niveau complet", (root_box.centerx, root_box.top + 42), theme.TEXT_DIM, center=True)

        children = sorted(tree.children, key=lambda node: node.score, reverse=tree.maximizing)[:12]
        box_w, box_h, gap = 150, 52, 12
        columns = 4
        total = columns * box_w + (columns - 1) * gap
        start_x = card.centerx - total // 2
        top = card.top + 218
        for index, node in enumerate(children):
            row, column = divmod(index, columns)
            x = start_x + column * (box_w + gap)
            y = top + row * (box_h + 74)
            box = pygame.Rect(x, y, box_w, box_h)
            pygame.draw.line(
                surface,
                theme.STROKE,
                (root_box.centerx, root_box.bottom),
                (box.centerx, box.top),
                1,
            )
            node_color = theme.POLICE if node.maximizing else theme.THIEF
            pygame.draw.rect(surface, theme.PANEL_SOFT, box, border_radius=8)
            pygame.draw.rect(surface, node_color, box, width=1, border_radius=8)
            if node.move is not None:
                text(
                    surface,
                    fonts.mono(11),
                    self._move_label(node.move),
                    (box.centerx, box.top + 7),
                    theme.TEXT_MUTED,
                    center=True,
                )
            text(
                surface,
                fonts.mono(14, bold=True),
                f"{node.score:+d}",
                (box.centerx, box.top + 24),
                self._score_color(node.score),
                center=True,
            )
            if node.cutoff:
                text(surface, fonts.mono(10), "coupure", (box.right - 8, box.top + 6), theme.WARNING, right=True)
            dots = min(8, len(node.children))
            for dot in range(dots):
                dx = box.centerx - (dots - 1) * 5 + dot * 10
                pygame.draw.circle(surface, node_color, (dx, box.bottom + 12), 2)
            if len(node.children) > 8:
                text(
                    surface,
                    fonts.mono(10),
                    f"+{len(node.children) - 8}",
                    (box.centerx + 46, box.bottom + 6),
                    theme.TEXT_DIM,
                )

        text(
            surface,
            fonts.mono(11),
            f"profondeur {result.depth} · {result.nodes} nœuds · {result.cutoffs} coupures"
            f" · {result.elapsed * 1000:.0f} ms · {len(tree.children)} coups racine",
            (card.centerx, card.bottom - 34),
            theme.TEXT_DIM,
            center=True,
        )

    # ------------------------------------------------------------------ résultat

    def _draw_result(self, surface: pygame.Surface) -> None:
        overlay = pygame.Surface(BOARD_AREA.size, pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 170))
        surface.blit(overlay, BOARD_AREA.topleft)
        card = pygame.Rect(0, 0, 584, 328)
        card.center = (BOARD_AREA.centerx, BOARD_AREA.centery)
        theme.panel(surface, card, fill=theme.PANEL, stroke=theme.STROKE, radius=20)

        fonts = self.app.fonts
        status = self.controller.status
        abandoned = getattr(self.controller, "abandoned", False)
        if abandoned:
            title, color = "CONNEXION PERDUE", theme.WARNING
        elif status is GameStatus.POLICE_WIN:
            title, color = "VICTOIRE POLICE", theme.POLICE
        elif status is GameStatus.THIEF_WIN:
            title, color = "VICTOIRE VOLEUR", theme.THIEF
        else:
            title, color = "MATCH NUL", theme.DRAW

        text(
            surface,
            fonts.mono(11, bold=True),
            "PARTIE INTERROMPUE" if abandoned else "PARTIE TERMINÉE",
            (card.centerx, card.top + 30),
            theme.TEXT_DIM,
            center=True,
        )
        text(surface, fonts.ui(34, bold=True), title, (card.centerx, card.top + 78), color, center=True)
        text(
            surface,
            fonts.ui(16),
            self.controller.status_headline(),
            (card.centerx, card.top + 120),
            theme.TEXT_MUTED,
            center=True,
        )
        text(
            surface,
            fonts.ui(14),
            self.controller.status_detail(),
            (card.centerx, card.top + 148),
            theme.TEXT_DIM,
            center=True,
        )
        text(
            surface,
            fonts.mono(13),
            f"demi-coups {self.controller.ply} · graine {self.controller.manager.seed}",
            (card.centerx, card.top + 180),
            theme.TEXT_DIM,
            center=True,
        )
        for button in self.overlay_buttons:
            button.draw(surface, fonts)

    # ------------------------------------------------------------------ helpers

    def _result_team(self) -> Team | None:
        result = self.controller.last_result
        if result is None or result.tree is None:
            return None
        return Team.POLICE if result.tree.maximizing else Team.THIEF

    def _value(self, result, getter) -> str:
        return "—" if result is None else getter(result)

    def _draw_fitted_text(
        self,
        surface: pygame.Surface,
        font: pygame.font.Font,
        value: str,
        pos: tuple[int, int],
        color: tuple[int, int, int],
        max_width: int,
        *,
        right: bool = False,
    ) -> pygame.Rect:
        rendered = font.render(value, True, color)
        if rendered.get_width() > max_width:
            ellipsis = "…"
            ellipsis_width = font.size(ellipsis)[0]
            low, high = 0, len(value)
            while low < high:
                middle = (low + high + 1) // 2
                if font.size(value[:middle])[0] + ellipsis_width <= max_width:
                    low = middle
                else:
                    high = middle - 1
            rendered = font.render(value[:low] + ellipsis, True, color)

        rect = rendered.get_rect()
        if right:
            rect.topright = pos
        else:
            rect.topleft = pos
        surface.blit(rendered, rect)
        return rect

    def _score_bar(self, surface: pygame.Surface, rect: pygame.Rect, score: int) -> None:
        pygame.draw.rect(surface, theme.STROKE_SOFT, rect, border_radius=rect.height // 2)
        center = rect.centerx
        span = clamp(abs(score) / 1200.0)
        width = round((rect.width / 2 - 2) * span)
        if width <= 0:
            return
        color = self._score_color(score)
        if score >= 0:
            bar = pygame.Rect(center, rect.top, width, rect.height)
        else:
            bar = pygame.Rect(center - width, rect.top, width, rect.height)
        pygame.draw.rect(surface, color, bar, border_radius=rect.height // 2)
        pygame.draw.line(
            surface,
            theme.TEXT_DIM,
            (center, rect.top - 2),
            (center, rect.bottom + 2),
            1,
        )

    @staticmethod
    def _score_color(score: int) -> tuple[int, int, int]:
        if score > 0:
            return theme.POLICE
        if score < 0:
            return theme.THIEF
        return theme.TEXT_MUTED

    @staticmethod
    def _move_label(move) -> str:
        if move.team is Team.POLICE:
            return f"P{(move.police_index or 0) + 1} {move.src}→{move.dst}"
        return f"{move.src}→{move.dst}"
