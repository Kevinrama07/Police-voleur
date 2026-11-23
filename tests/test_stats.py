"""Statistiques sauvegardées entre deux lancements."""

from core.constants import GameStatus
from stats import GameStats, StatsStore


def test_enregistrement_pour_un_mode(tmp_path):
    store = StatsStore(tmp_path / "stats.json")
    stats = store.record("solo", GameStatus.THIEF_WIN)
    assert stats.solo.games == 1
    assert stats.solo.thief_wins == 1
    assert stats.auto.games == 0

    reloaded = store.load()
    assert reloaded.solo.thief_wins == 1
    assert "Solo 1" in reloaded.summary()


def test_une_partie_en_cours_n_est_pas_comptee(tmp_path):
    store = StatsStore(tmp_path / "nested" / "stats.json")
    store.record("auto", GameStatus.ONGOING)
    assert store.load().auto.games == 0
    assert store.path.exists()


def test_fichier_corrompu_repart_de_zero(tmp_path):
    path = tmp_path / "stats.json"
    path.write_text("{pas du json", encoding="utf-8")
    assert StatsStore(path).load() == GameStats()
