"""Boucle principale, pile d'écrans et transitions (Pygame)."""

from __future__ import annotations

import sys
from typing import Callable

import pygame

from config import APP_TITLE, FPS, WINDOW_SIZE
from interface import theme
from interface.animations import Fade
from interface.theme import Fonts


class Scene:
    """Contrat minimal d'un écran."""

    def handle(self, event: pygame.event.Event) -> None:  # pragma: no cover - interface
        raise NotImplementedError

    def update(self, dt: float) -> None:  # pragma: no cover - interface
        raise NotImplementedError

    def draw(self, surface: pygame.Surface) -> None:  # pragma: no cover - interface
        raise NotImplementedError


class App:
    """Application : fenêtre, horloge, transitions et navigation entre écrans."""

    def __init__(self, settings) -> None:
        pygame.init()
        pygame.display.set_caption(APP_TITLE)
        self.screen = pygame.display.set_mode(WINDOW_SIZE)
        self.clock = pygame.time.Clock()
        self.fonts = Fonts()
        self.settings = settings
        self.running = True
        self.scene: Scene | None = None
        self._pending: Callable[[], Scene] | None = None
        self._fade: Fade | None = None
        self._clock_time = 0.0

    # ------------------------------------------------------------------ navigation

    def go_to(self, factory: Callable[[], Scene]) -> None:
        """Change d'écran avec fondu (le nouvel écran est construit après le noir)."""
        if self._fade is None and self._pending is None:
            self._pending = factory
            self._fade = Fade(0.14)

    def quit(self) -> None:
        self.running = False

    # ------------------------------------------------------------------ boucle

    def run(self, initial: Scene) -> None:
        self.scene = initial
        while self.running:
            dt = min(0.05, self.clock.tick(FPS) / 1000.0)
            self._clock_time += dt
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                    break
                if event.type == pygame.KEYDOWN and event.key == pygame.K_F11:
                    pygame.display.toggle_fullscreen()
                if self._fade is None and self.scene is not None:
                    self.scene.handle(event)
            if self.scene is not None:
                self.scene.update(dt)
            self._update_transition(dt)

            if self.scene is not None:
                self.scene.draw(self.screen)
            if self._fade is not None:
                overlay = pygame.Surface(self.screen.get_size())
                overlay.fill(theme.BG)
                overlay.set_alpha(self._fade.alpha)
                self.screen.blit(overlay, (0, 0))
            pygame.display.flip()

        pygame.quit()

    def _update_transition(self, dt: float) -> None:
        if self._fade is None:
            return
        self._fade.update(dt)
        if self._fade.phase == "in" and self._pending is not None:
            self.scene = self._pending()
            self._pending = None
        if self._fade.done:
            self._fade = None

    # ------------------------------------------------------------------ divers

    @property
    def time(self) -> float:
        return self._clock_time

    def toggle_fullscreen(self) -> None:
        pygame.display.toggle_fullscreen()


def run_app(settings) -> None:
    from interface.screens.menu import MainMenu

    app = App(settings)
    app.run(MainMenu(app))
    sys.exit(0)
