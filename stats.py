"""Statistiques locales sauvegardées en JSON, sans dépendance externe."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

from core.constants import GameStatus

DEFAULT_STATS_PATH = Path(
    os.getenv("POLICE_VOLEUR_STATS", Path.home() / ".police_voleur" / "stats.json")
)

MODE_LABELS = {
    "auto": "Auto",
    "solo": "Solo",
    "manuel": "Manuel",
    "network": "Réseau",
}


@dataclass(slots=True)
class ModeStats:
    """Compteurs d'un mode de jeu."""

    games: int = 0
    police_wins: int = 0
    thief_wins: int = 0
    draws: int = 0

    def record(self, status: GameStatus) -> None:
        if status is GameStatus.ONGOING:
            return
        self.games += 1
        if status is GameStatus.POLICE_WIN:
            self.police_wins += 1
        elif status is GameStatus.THIEF_WIN:
            self.thief_wins += 1
        elif status is GameStatus.DRAW:
            self.draws += 1

    def to_dict(self) -> dict[str, int]:
        return {
            "games": self.games,
            "police_wins": self.police_wins,
            "thief_wins": self.thief_wins,
            "draws": self.draws,
        }

    @classmethod
    def from_dict(cls, payload: object) -> "ModeStats":
        if not isinstance(payload, dict):
            return cls()
        return cls(
            games=int(payload.get("games", 0)),
            police_wins=int(payload.get("police_wins", 0)),
            thief_wins=int(payload.get("thief_wins", 0)),
            draws=int(payload.get("draws", 0)),
        )


@dataclass(slots=True)
class GameStats:
    """Statistiques agrégées par mode."""

    auto: ModeStats = field(default_factory=ModeStats)
    solo: ModeStats = field(default_factory=ModeStats)
    manuel: ModeStats = field(default_factory=ModeStats)
    network: ModeStats = field(default_factory=ModeStats)

    def for_mode(self, mode: str) -> ModeStats:
        return getattr(self, mode, self.auto)

    def record(self, mode: str, status: GameStatus) -> None:
        self.for_mode(mode).record(status)

    def summary(self) -> str:
        parts = []
        for mode, label in MODE_LABELS.items():
            counts = self.for_mode(mode)
            parts.append(
                f"{label} {counts.games} (P{counts.police_wins} V{counts.thief_wins} N{counts.draws})"
            )
        return " · ".join(parts)

    def to_dict(self) -> dict[str, dict[str, int]]:
        return {
            mode: self.for_mode(mode).to_dict()
            for mode in MODE_LABELS
        }

    @classmethod
    def from_dict(cls, payload: object) -> "GameStats":
        if not isinstance(payload, dict):
            return cls()
        return cls(
            auto=ModeStats.from_dict(payload.get("auto")),
            solo=ModeStats.from_dict(payload.get("solo")),
            manuel=ModeStats.from_dict(payload.get("manuel")),
            network=ModeStats.from_dict(payload.get("network")),
        )


class StatsStore:
    """Lecture/écriture atomique d'un petit fichier JSON local."""

    def __init__(self, path: Path | str | None = None) -> None:
        self.path = Path(path) if path is not None else DEFAULT_STATS_PATH

    def load(self) -> GameStats:
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            return GameStats()
        return GameStats.from_dict(payload)

    def save(self, stats: GameStats) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(stats.to_dict(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        temporary.replace(self.path)

    def record(self, mode: str, status: GameStatus) -> GameStats:
        stats = self.load()
        stats.record(mode, status)
        self.save(stats)
        return stats


__all__ = ["DEFAULT_STATS_PATH", "GameStats", "ModeStats", "StatsStore"]
