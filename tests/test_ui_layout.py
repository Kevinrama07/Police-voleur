"""Tests de non-chevauchement pour les écrans Pygame."""

from __future__ import annotations

from types import SimpleNamespace

import pygame

from config import GameSettings, WINDOW_SIZE
from core.constants import Team
from core.game_manager import GameManager
from core.graph import build_default_graph
from interface.screens import game as game_module
from interface.screens.game import GameScreen
from interface.screens.network_setup import NetworkSetup
from interface.screens.settings import SettingsScreen
from interface.theme import Fonts
from modes.multiplayer import NetworkController


def _app() -> SimpleNamespace:
    pygame.font.init()
    return SimpleNamespace(settings=GameSettings(), fonts=Fonts(), go_to=lambda _factory: None)


def test_settings_sliders_leave_space_for_labels() -> None:
    app = _app()
    screen = SettingsScreen(app)
    surface = pygame.Surface(WINDOW_SIZE)
    screen.draw(surface)

    label_height = app.fonts.ui(15).get_height()
    for slider in screen.sliders:
        label_bottom = slider.rect.top + label_height
        knob_top = slider.track.centery - 7
        assert label_bottom < knob_top, slider.label


def test_multiplayer_setup_has_host_join_and_no_address_inputs() -> None:
    screen = NetworkSetup(_app())
    try:
        assert (screen.host_button.label, screen.join_button.label) == (
            "Héberger",
            "Rejoindre",
        )
        assert not any(
            hasattr(screen, name) for name in ("host_port", "join_ip", "join_port")
        )
        assert not screen.host_button.rect.colliderect(screen.join_button.rect)
        assert screen.address_input.rect.colliderect(
            pygame.Rect(0, 0, *WINDOW_SIZE)
        )
        assert not screen.address_input.rect.colliderect(screen.connect_button.rect)
        screen.draw(pygame.Surface(WINDOW_SIZE))
    finally:
        screen.network.close()


def test_multiplayer_game_hud_fits_long_names_and_messages(
    monkeypatch,
) -> None:
    app = _app()
    graph = build_default_graph()
    manager = GameManager(graph, seed=3)

    class Network:
        role = Team.POLICE
        player_id = "P1"
        players = [
            {"player_id": "P1", "name": "Joueur 1", "role": "police"},
            {
                "player_id": "P2",
                "name": "Adversaire au nom exceptionnellement long",
                "role": "thief",
            },
        ]
        started = True
        connected = True
        game_id = "abcd1234"
        peer_left = False

        def close(self) -> None:
            pass

    controller = NetworkController(
        graph,
        app.settings,
        Network(),
        {"state": manager.state.to_dict(), "ply": 0, "seed": 3},
    )
    controller.note = "Message réseau particulièrement long " * 8
    screen = GameScreen(app, controller)
    rendered: list[tuple[str, pygame.Rect]] = []
    original_text = game_module.text
    original_pill = game_module.pill
    original_fitted_text = GameScreen._draw_fitted_text

    def capture_text(surface, font, value, pos, color=None, *, center=False, right=False):
        image = font.render(value, True, color or (255, 255, 255))
        rect = image.get_rect()
        if center:
            rect.center = pos
        elif right:
            rect.topright = pos
        else:
            rect.topleft = pos
        rendered.append((str(value), rect.copy()))
        surface.blit(image, rect)
        return rect

    def capture_pill(surface, fonts, value, center, color, *, filled=False):
        rect = original_pill(surface, fonts, value, center, color, filled=filled)
        rendered.append((str(value), rect.copy()))
        return rect

    def capture_fitted_text(self, surface, font, value, pos, color, max_width, *, right=False):
        rect = original_fitted_text(
            self, surface, font, value, pos, color, max_width, right=right
        )
        assert rect.width <= max_width
        rendered.append((str(value), rect.copy()))
        return rect

    monkeypatch.setattr(game_module, "text", capture_text)
    monkeypatch.setattr(game_module, "pill", capture_pill)
    monkeypatch.setattr(GameScreen, "_draw_fitted_text", capture_fitted_text)
    try:
        screen.draw(pygame.Surface(WINDOW_SIZE))
    finally:
        controller.close()

    for index, (first, first_rect) in enumerate(rendered):
        assert first_rect.left >= 0 and first_rect.right <= WINDOW_SIZE[0], first
        for second, second_rect in rendered[index + 1 :]:
            assert not first_rect.colliderect(second_rect), (
                first,
                first_rect,
                second,
                second_rect,
            )
