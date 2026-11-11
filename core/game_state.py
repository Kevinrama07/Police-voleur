"""État immuable du jeu et représentation d'un déplacement."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from core.constants import Team


@dataclass(frozen=True, slots=True)
class Move:
    """Déplacement d'un personnage vers un sommet voisin.

    Pour l'équipe POLICE, `police_index` désigne le policier déplacé (0, 1 ou 2).
    Pour le voleur, `police_index` vaut None.
    """

    team: Team
    src: str
    dst: str
    police_index: int | None = None

    def __post_init__(self) -> None:
        if self.team is Team.POLICE:
            if self.police_index not in (0, 1, 2):
                raise ValueError("un déplacement policier exige un index 0..2")
        elif self.police_index is not None:
            raise ValueError("le déplacement du voleur ne porte pas d'index")

    def to_dict(self) -> dict[str, Any]:
        return {
            "team": self.team.value,
            "src": self.src,
            "dst": self.dst,
            "police_index": self.police_index,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Move":
        return cls(
            team=Team(data["team"]),
            src=str(data["src"]),
            dst=str(data["dst"]),
            police_index=data.get("police_index"),
        )


@dataclass(frozen=True, slots=True)
class GameState:
    """État S = (V, P1, P2, P3, T) ; immuable pour permettre le partage sûr dans l'arbre Minimax."""

    thief: str
    police: tuple[str, str, str]
    turn: Team

    def __post_init__(self) -> None:
        if len(self.police) != 3:
            raise ValueError("exactement trois policiers")
        if len(set(self.police)) != 3:
            raise ValueError("positions des policiers distinctes")
        if self.thief in self.police:
            raise ValueError("le voleur ne peut partager un sommet avec un policier")

    def occupied(self) -> frozenset[str]:
        return frozenset((self.thief, *self.police))

    def police_at(self, index: int) -> str:
        return self.police[index]

    def thief_on_center(self) -> bool:
        from core.constants import CENTER

        return self.thief == CENTER

    def position_key(self) -> tuple[str, tuple[str, str, str], str]:
        """Clé de position (sans l'historique) pour la détection de répétitions."""
        return (self.thief, tuple(sorted(self.police)), self.turn.value)

    def to_dict(self) -> dict[str, Any]:
        return {
            "thief": self.thief,
            "police": list(self.police),
            "turn": self.turn.value,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "GameState":
        police = data["police"]
        if len(police) != 3:
            raise ValueError("exactement trois policiers")
        return cls(
            thief=str(data["thief"]),
            police=(str(police[0]), str(police[1]), str(police[2])),
            turn=Team(data["turn"]),
        )
