"""Intelligence artificielle : un contrat, deux minimax alpha-bêta."""

from ai.contrat import Bot, Context, MoveScore, Result, SearchNode, Stats
from ai.minimax_police import choose_move as police_bot
from ai.minimax_voleur import choose_move as thief_bot

__all__ = [
    "Bot",
    "Context",
    "MoveScore",
    "Result",
    "SearchNode",
    "Stats",
    "police_bot",
    "thief_bot",
]
