"""Menu principal : identité visuelle, navigation, aperçu animé du plateau."""

from __future__ import annotations

import pygame

from config import BOARD_IMAGE
from core.graph import build_default_graph
from interface import theme
from interface.animations import ease_out_cubic, pulse
from interface.app import App, Scene
from interface.board import BoardRenderer
from interface.components.controls import Button
from interface.theme import Fonts, text


class MainMenu(Scene):
    def __init__(self, app: App) -> None:
        self.app = app
        self.entry = 0.0
        self.clock = 0.0
        self.graph = build_default_graph()
        self.board = BoardRenderer(
            self.graph,
            pygame.Rect(742, 104, 466, 512),
            app.fonts,
            image_path=BOARD_IMAGE,
        )
        self.glow_vertices = [
            ("CENTER", theme.THIEF),
            ("EARt", theme.POLICE),
            ("EA6", theme.POLICE),
            ("J1", theme.POLICE),
        ]
        self.buttons = self._build_buttons()

    def _build_buttons(self) -> list[Button]:
        specs = [
            ("Démonstration", self._start_demo, True),
            ("Solo", self._start_solo, False),
            ("Multijoueur", self._start_multiplayer, False),
            ("Paramètres", self._open_settings, False),
            ("À propos", self._open_about, False),
            ("Quitter", self.app.quit, False),
        ]
        buttons: list[Button] = []
        for index, (label, action, primary) in enumerate(specs):
            buttons.append(
                Button(
                    rect=pygame.Rect(84, 280 + index * 61, 436, 52),
                    label=label,
                    primary=primary,
                    on_click=action,
                )
            )
        return buttons

    # ------------------------------------------------------------------ actions

    def _start_demo(self) -> None:
        from interface.screens.game import GameScreen
        from modes.demo import DemoController

        controller = DemoController(build_default_graph(), self.app.settings)
        self.app.go_to(lambda: GameScreen(self.app, controller))

    def _start_solo(self) -> None:
        from interface.screens.setup import SoloSetup

        self.app.go_to(lambda: SoloSetup(self.app))

    def _start_multiplayer(self) -> None:
        from interface.screens.network_setup import NetworkSetup

        self.app.go_to(lambda: NetworkSetup(self.app))

    def _open_settings(self) -> None:
        from interface.screens.settings import SettingsScreen

        self.app.go_to(lambda: SettingsScreen(self.app))

    def _open_about(self) -> None:
        from interface.screens.about import AboutScreen

        self.app.go_to(lambda: AboutScreen(self.app))

    # ------------------------------------------------------------------ scène

    def handle(self, event: pygame.event.Event) -> None:
        for button in self.buttons:
            button.handle(event)
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_RETURN:
                self._start_demo()
            elif event.key == pygame.K_ESCAPE:
                self.app.quit()

    def update(self, dt: float) -> None:
        self.entry = min(1.0, self.entry + dt * 1.6)
        self.clock += dt
        for button in self.buttons:
            button.update(dt)

    def draw(self, surface: pygame.Surface) -> None:
        surface.fill(theme.BG)
        self._draw_backdrop(surface)
        self._draw_identity(surface)
        for button in self.buttons:
            button.draw(surface, self.app.fonts)

    # ------------------------------------------------------------------ dessin

    def _draw_backdrop(self, surface: pygame.Surface) -> None:
        horizon = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
        for index in range(0, 900, 60):
            alpha = max(0, 22 - index // 45)
            pygame.draw.line(
                horizon,
                (*theme.BOARD_GLOW, alpha),
                (0, 120 + index),
                (surface.get_width(), 120 + index),
                1,
            )
        surface.blit(horizon, (0, 0))

        panel = pygame.Rect(700, 64, 520, 600)
        theme.panel(surface, panel, fill=theme.BG_SOFT, stroke=theme.STROKE_SOFT, radius=22)
        surface.blit(self.board.surface, (742, 104))

        breathe = 0.4 + 0.6 * pulse(0.18)
        for vertex, color in self.glow_vertices:
            x, y = self.board.screen_pos(vertex)
            x += 742
            y += 104
            ring = 7 + 5 * pulse(0.5, phase=hash(vertex) % 7)
            theme.alpha_disc(surface, (round(x), round(y)), int(ring * 1.6), (*color, int(45 * breathe)))
            pygame.draw.circle(surface, color, (round(x), round(y)), int(ring * 0.55), 0)
            pygame.draw.circle(surface, (*color, 120), (round(x), round(y)), int(ring), 1)

    def _draw_identity(self, surface: pygame.Surface) -> None:
        reveal = ease_out_cubic(self.entry)
        y_offset = int((1 - reveal) * 14)

        text(surface, self.app.fonts.title(76), "POLICE", (80, 20 + y_offset), theme.STROKE)
        text(surface, self.app.fonts.title(76), "VOLEUR", (80, 100 + y_offset), theme.THIEF)
        pygame.draw.line(
            surface,
            theme.TEXT,
            (86, 200 + y_offset),
            (430, 200 + y_offset),
            2,
        )

        for index, button in enumerate(self.buttons):
            button.rect.y = 280 + index * 61 + int((1 - reveal) * (18 + index * 4))