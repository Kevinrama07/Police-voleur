"""Point d'entrée de l'application POLICE – VOLEUR."""

from __future__ import annotations

import argparse
from collections.abc import Sequence

from config import GameSettings
from core.constants import Team
from core.graph import build_default_graph
from interface.app import App, Scene, run_app
from match import Mode

NETWORK_MODE = "multijoueur"


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="POLICE – VOLEUR")
    parser.add_argument(
        "--mode",
        choices=[*map(lambda mode: mode.value, Mode), NETWORK_MODE],
        help="démarre directement une partie sans passer par le menu",
    )
    parser.add_argument(
        "--role",
        choices=("host", "join"),
        help="avec --mode multijoueur : héberge ou rejoint sans saisir d'adresse IP",
    )
    parser.add_argument(
        "--human-team",
        choices=("thief", "police"),
        help="avec --mode manuel : joue le camp indiqué, l'IA prend l'autre",
    )
    parser.add_argument("--seed", type=int, help="graine de la partie")
    args = parser.parse_args(argv)
    if args.role is not None and args.mode != NETWORK_MODE:
        parser.error("--role ne s'utilise qu'avec --mode multijoueur")
    if args.human_team is not None and args.mode != Mode.MANUEL.value:
        parser.error("--human-team ne s'utilise qu'avec --mode manuel")

    settings = GameSettings(seed=args.seed)
    initial = None
    if args.mode == NETWORK_MODE:

        def initial(app: App) -> Scene:
            from interface.screens.network_setup import NetworkSetup

            return NetworkSetup(app, auto_role=args.role)

    elif args.mode is not None:
        mode = Mode(args.mode)

        def initial(app: App) -> Scene:
            from interface.screens.game import GameScreen
            from match import MatchController

            human_team = None
            if args.human_team is not None:
                human_team = Team.THIEF if args.human_team == "thief" else Team.POLICE
            controller = MatchController(
                build_default_graph(),
                app.settings,
                mode=mode,
                human_team=human_team,
            )
            return GameScreen(app, controller)

    run_app(settings, initial)


if __name__ == "__main__":
    main()
