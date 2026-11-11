"""Mode Démonstration : deux IA s'affrontent avec le même moteur et la même IA."""

from __future__ import annotations

from config import GameSettings
from core.graph import Graph
from modes.match_controller import MatchController


class DemoController(MatchController):
    """IA POLICE contre IA VOLEUR ; aucun camp humain."""

    kind = "demo"

    def __init__(self, graph: Graph, settings: GameSettings) -> None:
        super().__init__(graph, settings, human_team=None)

    @property
    def mode_name(self) -> str:
        return "Démonstration"
