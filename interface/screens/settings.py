"""Écran Paramètres : IA, démonstration et règles configurables."""

from __future__ import annotations

import pygame

from config import DEMO_STEP_DELAY_SECONDS, GameSettings
from core.constants import (
    DEFAULT_MAX_MOVES,
    DEFAULT_REPETITION_LIMIT,
    DEFAULT_RETURN_COOLDOWN,
)
from interface import theme
from interface.app import App, Scene
from interface.components.controls import Button, Slider, Toggle
from interface.theme import text


class SettingsScreen(Scene):
    def __init__(self, app: App) -> None:
        self.app = app
        self.settings = app.settings
        self.buttons = [
            Button(
                rect=pygame.Rect(120, 700, 190, 46),
                label="Retour",
                on_click=self._back,
            ),
            Button(
                rect=pygame.Rect(326, 700, 220, 46),
                label="Réinitialiser",
                on_click=self._reset,
            ),
        ]
        self.sliders = self._build_sliders()
        self.toggles = self._build_toggles()

    def _build_sliders(self) -> list[Slider]:
        settings = self.settings
        return [
            Slider(
                rect=pygame.Rect(170, 236, 420, 60),
                label="Profondeur Minimax",
                minimum=2,
                maximum=6,
                step=1,
                value=settings.ai_depth,
                formatter=lambda v: f"{int(v)} demi-coups",
                on_change=lambda v: setattr(settings, "ai_depth", int(v)),
            ),
            Slider(
                rect=pygame.Rect(170, 314, 420, 60),
                label="Temps de réflexion max.",
                minimum=0.25,
                maximum=4.0,
                step=0.25,
                value=settings.ai_time_limit,
                formatter=lambda v: f"{v:.2f} s",
                on_change=lambda v: setattr(settings, "ai_time_limit", float(v)),
            ),
            Slider(
                rect=pygame.Rect(170, 392, 420, 60),
                label="Vitesse de la démo",
                minimum=0.5,
                maximum=4.0,
                step=0.25,
                value=settings.demo_speed,
                formatter=lambda v: f"×{v:.2f}  ({DEMO_STEP_DELAY_SECONDS / v:.2f} s/coup)",
                on_change=lambda v: setattr(settings, "demo_speed", float(v)),
            ),
            Slider(
                rect=pygame.Rect(170, 470, 420, 60),
                label="Graine aléatoire",
                minimum=0,
                maximum=200,
                step=1,
                value=0 if settings.seed is None else settings.seed,
                formatter=lambda v: "aléatoire" if int(v) == 0 else f"graine {int(v)}",
                on_change=lambda v: setattr(settings, "seed", None if int(v) == 0 else int(v)),
            ),
            Slider(
                rect=pygame.Rect(720, 236, 400, 60),
                label="Cooldown de retour au centre",
                minimum=0,
                maximum=20,
                step=1,
                value=settings.return_cooldown,
                formatter=lambda v: f"{int(v)} demi-coups",
                on_change=lambda v: setattr(settings, "return_cooldown", int(v)),
            ),
            Slider(
                rect=pygame.Rect(720, 340, 400, 60),
                label="Nulle par répétition",
                minimum=0,
                maximum=10,
                step=1,
                value=settings.repetition_limit,
                formatter=lambda v: "désactivée" if int(v) == 0 else f"{int(v)} occurrences",
                on_change=lambda v: setattr(settings, "repetition_limit", int(v)),
            ),
            Slider(
                rect=pygame.Rect(720, 418, 400, 60),
                label="Limite de coups",
                minimum=0,
                maximum=1000,
                step=50,
                value=settings.max_moves,
                formatter=lambda v: "illimitée" if int(v) == 0 else f"{int(v)} coups",
                on_change=lambda v: setattr(settings, "max_moves", int(v)),
            ),
        ]

    def _build_toggles(self) -> list[Toggle]:
        settings = self.settings
        return [
            Toggle(
                rect=pygame.Rect(720, 500, 400, 42),
                label="Centre contestable",
                description="La police peut occuper le centre après le départ du voleur",
                value=settings.center_contestable,
                on_change=lambda v: setattr(settings, "center_contestable", bool(v)),
            ),
        ]

    # ------------------------------------------------------------------ actions

    def _back(self) -> None:
        from interface.screens.menu import MainMenu

        self.app.go_to(lambda: MainMenu(self.app))

    def _reset(self) -> None:
        defaults = GameSettings()
        for name in (
            "ai_depth",
            "ai_time_limit",
            "demo_speed",
            "seed",
            "return_cooldown",
            "center_contestable",
            "repetition_limit",
            "max_moves",
        ):
            setattr(self.settings, name, getattr(defaults, name))
        self.app.go_to(lambda: SettingsScreen(self.app))

    # ------------------------------------------------------------------ scène

    def handle(self, event: pygame.event.Event) -> None:
        for control in (*self.sliders, *self.toggles, *self.buttons):
            control.handle(event)
        if event.type == pygame.KEYDOWN and event.key in (pygame.K_ESCAPE, pygame.K_LEFT):
            self._back()

    def update(self, dt: float) -> None:
        for control in (*self.sliders, *self.toggles, *self.buttons):
            if hasattr(control, "update"):
                control.update(dt)

    def draw(self, surface: pygame.Surface) -> None:
        surface.fill(theme.BG)
        text(surface, self.app.fonts.title(44), "Paramètres", (120, 74), theme.TEXT)
        text(
            surface,
            self.app.fonts.ui(16),
            "Les réglages s'appliquent aux prochaines parties (le moteur reste inchangé pendant une partie).",
            (120, 132),
            theme.TEXT_MUTED,
        )

        left = pygame.Rect(140, 186, 480, 420)
        right = pygame.Rect(690, 186, 460, 400)
        theme.panel(surface, left, fill=theme.BG_SOFT)
        theme.panel(surface, right, fill=theme.BG_SOFT)
        theme.tracking_text(
            surface, self.app.fonts.ui(12, bold=True), "INTELLIGENCE ARTIFICIELLE",
            (170, 210), theme.TEXT_DIM, 2,
        )
        theme.tracking_text(
            surface, self.app.fonts.ui(12, bold=True), "RÈGLES DE PARTIE",
            (720, 210), theme.TEXT_DIM, 2,
        )
        for slider in self.sliders:
            slider.draw(surface, self.app.fonts)
        for toggle in self.toggles:
            toggle.draw(surface, self.app.fonts)

        note = pygame.Rect(720, 566, 400, 96)
        theme.panel(surface, note, fill=theme.PANEL, radius=10)
        if self.settings.return_cooldown <= 0:
            lines = [
                "Cooldown désactivé : le voleur peut",
                "revenir au centre immédiatement",
                "après l'avoir quitté.",
            ]
        else:
            lines = [
                f"Un cooldown de {self.settings.return_cooldown} empêche le vol humain",
                "du retour immédiat au centre et rend la",
                "partie réellement disputée.",
            ]
        for index, line in enumerate(lines):
            text(surface, self.app.fonts.ui(13), line, (736, 578 + index * 20), theme.TEXT_DIM)

        for button in self.buttons:
            button.draw(surface, self.app.fonts)
        text(
            surface,
            self.app.fonts.mono(12),
            "Échap : retour au menu",
            (1000, 716),
            theme.TEXT_DIM,
        )
