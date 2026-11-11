"""Écran À propos : présentation du projet et des algorithmes."""

from __future__ import annotations

import pygame

from config import APP_VERSION
from interface import theme
from interface.app import App, Scene
from interface.components.controls import Button
from interface.theme import text


BLOCKS = [
    (
        "LE PLATEAU",
        [
            "L'image d'origine a été analysée pixel par pixel : ellipse,",
            "cordes verticale et horizontale, cercle central et huit arcs",
            "de raccord. Le graphe en est déduit : 21 sommets, 36 arêtes,",
            "fidélité mesurée à 1,4 px en moyenne sur l'encre.",
            "Aucune position n'est inventée ; le rendu réutilise les",
            "mêmes primitives géométriques que l'analyse.",
        ],
    ),
    (
        "L'INTELLIGENCE ARTIFICIELLE",
        [
            "Minimax explore l'arbre réel des coups légaux : la police",
            "maximise, le voleur minimise. Alpha-Beta élague les branches",
            "inutiles, l'ordre des coups et une table de transposition",
            "accélèrent la recherche. L'évaluation combine distances BFS,",
            "mobilité, pression sur le chemin du centre et contrôle du",
            "centre. Les scores terminaux ±10 000 sont prioritaires.",
        ],
    ),
    (
        "LES TROIS MODES",
        [
            "Démonstration : deux IA s'affrontent, avec panneau de",
            "visualisation (nœuds, coupures, temps) et arbre Minimax.",
            "Solo : jouez le voleur ou la police contre l'IA.",
            "Multijoueur : deux machines sur le même réseau local,",
            "serveur autoritaire en Socket TCP, messages JSON.",
        ],
    ),
    (
        "LES RÈGLES",
        [
            "Le voleur part du centre et gagne en y revenant après",
            "l'avoir quitté. La police gagne en bloquant tous ses",
            "déplacements. Le centre reste interdit au départ aux",
            "policiers, mais devient contestable après le départ du",
            "voleur, avec un cooldown de retour configurable : sans",
            "cela, le voleur gagnait toujours en trois demi-coups.",
        ],
    ),
]

class AboutScreen(Scene):
    def __init__(self, app: App) -> None:
        self.app = app
        self.button = Button(
            rect=pygame.Rect(120, 700, 190, 46), label="Retour", on_click=self._back
        )

    def _back(self) -> None:
        from interface.screens.menu import MainMenu

        self.app.go_to(lambda: MainMenu(self.app))

    def handle(self, event: pygame.event.Event) -> None:
        self.button.handle(event)
        if event.type == pygame.KEYDOWN and event.key in (pygame.K_ESCAPE, pygame.K_LEFT):
            self._back()

    def update(self, dt: float) -> None:
        self.button.update(dt)

    def draw(self, surface: pygame.Surface) -> None:
        surface.fill(theme.BG)
        text(surface, self.app.fonts.title(44), "À propos", (120, 74), theme.TEXT)
        text(
            surface,
            self.app.fonts.ui(16),
            "POLICE – VOLEUR, projet universitaire : graphes, BFS, Minimax, Alpha-Beta et réseau TCP.",
            (120, 132),
            theme.TEXT_MUTED,
        )

        for index, (title, lines) in enumerate(BLOCKS):
            column = index % 2
            row = index // 2
            x = 120 + column * 540
            y = 186 + row * 246
            rect = pygame.Rect(x, y, 500, 224)
            theme.panel(surface, rect, fill=theme.BG_SOFT)
            theme.tracking_text(
                surface, self.app.fonts.ui(12, bold=True), title, (x + 24, y + 18),
                theme.POLICE, 2,
            )
            for line_index, line in enumerate(lines):
                text(
                    surface,
                    self.app.fonts.ui(14),
                    line,
                    (x + 24, y + 48 + line_index * 21),
                    theme.TEXT_MUTED,
                )

        text(surface, self.app.fonts.mono(12), f"v{APP_VERSION}", (1210, 716), theme.TEXT_DIM)
        self.button.draw(surface, self.app.fonts)
