"""Écran de préparation du mode solo : choix du camp joué par l'humain."""

from __future__ import annotations

import pygame

from config import BOARD_IMAGE
from core.constants import Team
from core.graph import build_default_graph
from interface import theme
from interface.animations import pulse
from interface.app import App, Scene
from interface.board import BoardRenderer
from interface.components.controls import Button
from interface.theme import text


class SoloSetup(Scene):
    def __init__(self, app: App) -> None:
        self.app = app
        self.graph = build_default_graph()
        self.hover: str | None = None
        self.clock = 0.0
        self.cards = [
            (
                "thief",
                pygame.Rect(120, 296, 286, 306),
                "VOLEUR",
                theme.THIEF,
                "Fuir les trois policiers",
                "et regagner le centre après",
                "le cooldown de retour.",
                Team.THIEF,
            ),
            (
                "police",
                pygame.Rect(436, 296, 286, 306),
                "POLICE",
                theme.POLICE,
                "Coordonner trois unités",
                "pour bloquer tous les",
                "déplacements du voleur.",
                Team.POLICE,
            ),
        ]
        self.buttons = [
            Button(rect=pygame.Rect(120, 694, 190, 46), label="Retour", on_click=self._back),
        ]
        self.board = BoardRenderer(
            self.graph,
            pygame.Rect(790, 150, 400, 520),
            app.fonts,
            image_path=BOARD_IMAGE,
        )

    # ------------------------------------------------------------------ actions

    def _start(self, team: Team) -> None:
        from interface.screens.game import GameScreen
        from modes.single_player import SinglePlayerController

        controller = SinglePlayerController(self.graph, self.app.settings, human_team=team)
        self.app.go_to(lambda: GameScreen(self.app, controller))

    def _back(self) -> None:
        from interface.screens.menu import MainMenu

        self.app.go_to(lambda: MainMenu(self.app))

    # ------------------------------------------------------------------ scène

    def handle(self, event: pygame.event.Event) -> None:
        for button in self.buttons:
            button.handle(event)
        if event.type == pygame.MOUSEMOTION:
            self.hover = next(
                (key for key, rect, *_ in self.cards if rect.collidepoint(event.pos)),
                None,
            )
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for key, rect, _title, _color, _l1, _l2, _l3, team in self.cards:
                if rect.collidepoint(event.pos):
                    self._start(team)
                    return
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self._back()
            elif event.key in (pygame.K_1, pygame.K_v):
                self._start(Team.THIEF)
            elif event.key in (pygame.K_2, pygame.K_p):
                self._start(Team.POLICE)

    def update(self, dt: float) -> None:
        self.clock += dt
        for button in self.buttons:
            button.update(dt)

    # ------------------------------------------------------------------ dessin

    def draw(self, surface: pygame.Surface) -> None:
        surface.fill(theme.BG)
        self._draw_backdrop(surface)
        fonts = self.app.fonts

        text(surface, fonts.title(46), "Solo", (118, 96), theme.TEXT)
        text(
            surface,
            fonts.ui(16),
            "Choisissez votre camp : l'IA joue l'autre avec le même moteur et les mêmes règles.",
            (120, 168),
            theme.TEXT_MUTED,
        )

        for key, rect, title, color, line1, line2, line3, _team in self.cards:
            self._draw_card(surface, key, rect, title, color, (line1, line2, line3))

        for button in self.buttons:
            button.draw(surface, fonts)

        panel = pygame.Rect(760, 120, 460, 580)
        theme.panel(surface, panel, fill=theme.BG_SOFT, stroke=theme.STROKE_SOFT, radius=22)
        surface.blit(self.board.surface, (790, 150))

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

    def _draw_card(
        self,
        surface: pygame.Surface,
        key: str,
        rect: pygame.Rect,
        title: str,
        color: tuple[int, int, int],
        lines: tuple[str, str, str],
    ) -> None:
        fonts = self.app.fonts
        hovered = self.hover == key
        fill = theme.PANEL_HOVER if hovered else theme.PANEL
        theme.panel(
            surface,
            rect,
            fill=fill,
            stroke=color if hovered else theme.STROKE_SOFT,
            radius=18,
            width=2 if hovered else 1,
        )
        center_x = rect.centerx
        icon_y = rect.top + 82
        glow = int(80 + 70 * pulse(0.4, 0.3 if key == "thief" else 0.0)) if hovered else 46
        theme.alpha_disc(surface, (center_x, icon_y), 54, (*color, glow))
        pygame.draw.circle(surface, color, (center_x, icon_y), 26)
        pygame.draw.circle(surface, theme.BG, (center_x, icon_y), 26, 4)
        pygame.draw.circle(surface, theme.TEXT, (center_x - 8, icon_y - 9), 7)

        text(surface, fonts.ui(27, bold=True), title, (center_x, rect.top + 132), theme.TEXT, center=True)
        for index, line in enumerate(lines):
            text(
                surface,
                fonts.ui(14),
                line,
                (center_x, rect.top + 176 + index * 22),
                theme.TEXT_MUTED,
                center=True,
            )
        action = pygame.Rect(rect.left + 40, rect.bottom - 60, rect.width - 80, 38)
        pygame.draw.rect(surface, color if hovered else theme.STROKE, action, width=1, border_radius=10)
        text(
            surface,
            fonts.ui(15, bold=True),
            "Jouer ce camp →",
            (action.centerx, action.centery),
            color if hovered else theme.TEXT_MUTED,
            center=True,
        )
