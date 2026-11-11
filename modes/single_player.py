"""Mode Solo : un humain (voleur ou police) contre l'IA."""

from __future__ import annotations

from config import GameSettings
from core.constants import Team
from core.graph import Graph
from modes.match_controller import MatchController


class SinglePlayerController(MatchController):
    """Humain contre IA ; l'IA joue le camp opposé avec les règles communes."""

    kind = "solo"

    def __init__(
        self, graph: Graph, settings: GameSettings, human_team: Team
    ) -> None:
        super().__init__(graph, settings, human_team=human_team)

    @property
    def mode_name(self) -> str:
        return "Solo"
