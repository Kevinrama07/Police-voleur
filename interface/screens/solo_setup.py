"""Configuration du mode Solo : le joueur choisit son camp, l'IA prend l'autre."""

from __future__ import annotations

import pygame

from core.constants import Team
from core.graph import build_default_graph
from interface import theme
from interface.app import App, Scene
from interface.components.controls import Button
from interface.theme import text


class SoloSetup(Scene):
    def __init__(self, app: App) -> None:
        self.app = app
        self.buttons = [
            Button(
                rect=pygame.Rect(112, 282, 500, 156),
                label="JOUER LE VOLEUR",
                primary=True,
                on_click=lambda: self._start(Team.THIEF),
            ),
            Button(
                rect=pygame.Rect(668, 282, 500, 156),
                label="JOUER LA POLICE",
                on_click=lambda: self._start(Team.POLICE),
            ),
            Button(
                rect=pygame.Rect(84, 700, 220, 48),
                label="Retour",
                on_click=self._back,
            ),
        ]

    def _start(self, team: Team) -> None:
        from interface.screens.game import GameScreen
        from match import MatchController, Mode

        controller = MatchController(
            build_default_graph(),
            self.app.settings,
            mode=Mode.MANUEL,
            human_team=team,
        )
        self.app.go_to(lambda: GameScreen(self.app, controller))

    def _back(self) -> None:
        from interface.screens.menu import MainMenu

        self.app.go_to(lambda: MainMenu(self.app))

    def handle(self, event: pygame.event.Event) -> None:
        for button in self.buttons:
            button.handle(event)
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self._back()

    def update(self, dt: float) -> None:
        for button in self.buttons:
            button.update(dt)

    def draw(self, surface: pygame.Surface) -> None:
        surface.fill(theme.BG)
        theme.panel(
            surface,
            pygame.Rect(64, 52, 1148, 624),
            fill=theme.BG_SOFT,
            stroke=theme.STROKE_SOFT,
            radius=20,
        )
        text(surface, self.app.fonts.title(62), "MODE SOLO", (112, 96), theme.TEXT)
        text(
            surface,
            self.app.fonts.ui(18),
            "Choisissez votre camp : l'adversaire est joué par le minimax correspondant.",
            (112, 178),
            theme.TEXT_MUTED,
        )

        text(surface, self.app.fonts.ui(13, bold=True), "VOLEUR", (112, 248), theme.THIEF)
        text(surface, self.app.fonts.ui(13, bold=True), "POLICE", (668, 248), theme.POLICE)
        for button in self.buttons[:2]:
            button.draw(surface, self.app.fonts)

        text(
            surface,
            self.app.fonts.ui(15),
            "Vous cliquez sur les sommets pour déplacer vos pions. L'IA répond automatiquement.",
            (112, 490),
            theme.TEXT_MUTED,
        )
        text(
            surface,
            self.app.fonts.mono(13),
            f"Profondeur Minimax : {self.app.settings.ai_depth} · temps max : {self.app.settings.ai_time_limit:g} s",
            (112, 524),
            theme.TEXT_DIM,
        )
        self.buttons[2].draw(surface, self.app.fonts)


__all__ = ["SoloSetup"]
