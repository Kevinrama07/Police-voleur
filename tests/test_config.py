"""Phase 0 : les réglages ont un seul point de traduction vers le moteur."""

from ai.contrat import Context
from config import Difficulty, GameSettings
from core.constants import (
    DEFAULT_CENTER_CONTESTABLE,
    DEFAULT_MAX_MOVES,
    DEFAULT_REPETITION_LIMIT,
    DEFAULT_RETURN_COOLDOWN,
)
from core.ruleset import RuleSet


def test_settings_to_rules_mappe_les_regles():
    settings = GameSettings(return_cooldown=3, center_contestable=False)
    assert settings.to_rules() == RuleSet(return_cooldown=3, center_contestable=False)


def test_settings_to_game_config_mappe_les_limites():
    settings = GameSettings(
        max_moves=12, repetition_limit=2, return_cooldown=1, center_contestable=False
    )
    config = settings.to_game_config()
    assert (config.max_moves, config.repetition_limit) == (12, 2)
    assert config.rules.return_cooldown == 1
    assert config.rules.center_contestable is False


def test_valeurs_par_defaut_identiques_au_moteur():
    settings = GameSettings()
    assert settings.return_cooldown == DEFAULT_RETURN_COOLDOWN
    assert settings.center_contestable is DEFAULT_CENTER_CONTESTABLE
    assert settings.repetition_limit == DEFAULT_REPETITION_LIMIT
    assert settings.max_moves == DEFAULT_MAX_MOVES
    assert settings.difficulty is Difficulty.NORMAL


def test_contrat_des_bots_transporte_le_contexte():
    context = Context(history=(), repetition_limit=3, deadline=None)
    assert context.repetition_limit == 3
    assert Context().history == ()


def test_les_presets_de_difficulte_changent_ia_et_regles():
    settings = GameSettings()
    settings.apply_difficulty(Difficulty.FACILE)
    assert (settings.ai_depth, settings.return_cooldown) == (2, DEFAULT_RETURN_COOLDOWN + 2)
    settings.apply_difficulty("difficile")
    assert (settings.ai_depth, settings.ai_time_limit) == (4, 4.0)
    assert settings.return_cooldown == DEFAULT_RETURN_COOLDOWN - 2


def test_un_reglage_manuel_marque_la_difficulte_personnalisee():
    settings = GameSettings()
    settings.ai_depth = 5
    settings.mark_custom()
    assert settings.difficulty is Difficulty.PERSONNALISE
