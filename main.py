"""Point d'entrée de l'application POLICE – VOLEUR."""

from __future__ import annotations

from config import GameSettings
from interface.app import run_app


def main() -> None:
    run_app(GameSettings())


if __name__ == "__main__":
    main()
