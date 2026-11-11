"""Jeu de règles configurable (valeurs par défaut : voir `docs/GRAPH_MODEL.md` §6)."""

from __future__ import annotations

from dataclasses import dataclass

from core.constants import DEFAULT_RETURN_COOLDOWN


@dataclass(frozen=True, slots=True)
class RuleSet:
    """Règles ajustables sans toucher au moteur.

    `return_cooldown` : nombre de demi-coups devant être joués avant que le voleur
    puisse légalement revenir au centre (0 = retour autorisé immédiatement).

    `center_contestable` : les policiers peuvent-ils occuper le centre après le
    départ du voleur ? Si False, le centre reste strictement réservé au voleur
    (règle littérale du prompt, qui rend la victoire policière impossible).
    """

    return_cooldown: int = DEFAULT_RETURN_COOLDOWN
    center_contestable: bool = True

    def thief_can_return(self, ply: int) -> bool:
        return ply >= max(0, self.return_cooldown)


DEFAULT_RULES = RuleSet()
