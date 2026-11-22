"""Façade réseau minimale : deux PC, hôte autoritaire, transport TCP existant."""

from modes.multiplayer import NetworkController
from multiplayer.network_manager import NetworkManager

__all__ = ["NetworkController", "NetworkManager"]
