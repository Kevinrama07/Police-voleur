"""Graphe du plateau : unique source de vérité des déplacements.

Coordonnées dans le repère de l'image de référence (689 x 796, y vers le bas).
Aucune dépendance à Pygame ni à un outil de rendu.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Iterable, Iterator, Mapping

from core.constants import CENTER

VERTEX_POSITIONS: dict[str, tuple[float, float]] = {
    "T": (352.0, 189.6),
    "EA2": (276.4, 202.8),
    "EALt": (155.0, 322.6),
    "L": (138.1, 406.5),
    "EALb": (157.5, 500.4),
    "EA6": (269.3, 611.4),
    "B": (352.0, 627.5),
    "EA7": (434.6, 608.4),
    "EARb": (545.4, 486.0),
    "R": (559.0, 406.5),
    "EARt": (542.9, 324.5),
    "EA1": (431.2, 207.2),
    "J1": (352.0, 272.7),
    "VCt": (352.0, 365.3),
    "CENTER": (352.0, 406.5),
    "VCb": (352.0, 446.8),
    "J2": (352.0, 550.0),
    "HAL": (225.3, 406.5),
    "HCl": (311.8, 406.5),
    "HCr": (393.3, 406.5),
    "HAR": (476.1, 406.5),
}

EDGE_PRIMITIVES: tuple[tuple[str, str, str], ...] = (
    ("L", "EALt", "E"),
    ("EALt", "EA2", "E"),
    ("EA2", "T", "E"),
    ("T", "EA1", "E"),
    ("EA1", "EARt", "E"),
    ("EARt", "R", "E"),
    ("R", "EARb", "E"),
    ("EARb", "EA7", "E"),
    ("EA7", "B", "E"),
    ("B", "EA6", "E"),
    ("EA6", "EALb", "E"),
    ("EALb", "L", "E"),
    ("T", "J1", "V"),
    ("J1", "VCt", "V"),
    ("VCt", "CENTER", "V"),
    ("CENTER", "VCb", "V"),
    ("VCb", "J2", "V"),
    ("J2", "B", "V"),
    ("L", "HAL", "H"),
    ("HAL", "HCl", "H"),
    ("HCl", "CENTER", "H"),
    ("CENTER", "HCr", "H"),
    ("HCr", "HAR", "H"),
    ("HAR", "R", "H"),
    ("VCt", "HCr", "C"),
    ("HCr", "VCb", "C"),
    ("VCb", "HCl", "C"),
    ("HCl", "VCt", "C"),
    ("J1", "EA1", "A1"),
    ("J1", "EA2", "A2"),
    ("J2", "EA6", "A6"),
    ("J2", "EA7", "A7"),
    ("EALt", "HAL", "ALU"),
    ("HAL", "EALb", "ALL"),
    ("EARt", "HAR", "ARU"),
    ("HAR", "EARb", "ARL"),
)

PRIMITIVE_EDGE_COUNTS: dict[str, int] = {
    "E": 12,
    "V": 6,
    "H": 6,
    "C": 4,
    "A1": 1,
    "A2": 1,
    "A6": 1,
    "A7": 1,
    "ALU": 1,
    "ALL": 1,
    "ARU": 1,
    "ARL": 1,
}


@dataclass(frozen=True, slots=True)
class Vertex:
    """Sommet du graphe : identifiant unique et coordonnées de référence."""

    id: str
    x: float
    y: float

    @property
    def position(self) -> tuple[float, float]:
        return (self.x, self.y)


@dataclass(frozen=True, slots=True)
class Edge:
    """Arête non orientée associée à la primitive dessinée qui la porte."""

    u: str
    v: str
    primitive: str

    def connects(self, a: str, b: str) -> bool:
        return (self.u == a and self.v == b) or (self.u == b and self.v == a)


class Graph:
    """Graphe non orienté avec liste d'adjacence."""

    def __init__(
        self,
        positions: Mapping[str, tuple[float, float]],
        edges: Iterable[tuple[str, str, str]],
    ) -> None:
        self._vertices: dict[str, Vertex] = {
            vid: Vertex(vid, float(x), float(y)) for vid, (x, y) in positions.items()
        }
        self._edges: list[Edge] = [Edge(u, v, p) for u, v, p in edges]
        adjacency: dict[str, list[str]] = {vid: [] for vid in self._vertices}
        seen: set[tuple[str, str]] = set()
        for edge in self._edges:
            if edge.u not in self._vertices or edge.v not in self._vertices:
                raise ValueError(f"arête invalide: {edge.u}-{edge.v}")
            if edge.u == edge.v:
                raise ValueError(f"boucle interdite: {edge.u}")
            key = tuple(sorted((edge.u, edge.v)))
            if key in seen:
                raise ValueError(f"arête dupliquée: {edge.u}-{edge.v}")
            seen.add(key)
            adjacency[edge.u].append(edge.v)
            adjacency[edge.v].append(edge.u)
        self._adjacency: dict[str, tuple[str, ...]] = {
            vid: tuple(sorted(neighbors)) for vid, neighbors in adjacency.items()
        }

    @property
    def vertices(self) -> Mapping[str, Vertex]:
        return self._vertices

    @property
    def edges(self) -> tuple[Edge, ...]:
        return tuple(self._edges)

    @property
    def center(self) -> str:
        return CENTER

    def __len__(self) -> int:
        return len(self._vertices)

    def __iter__(self) -> Iterator[str]:
        return iter(self._vertices)

    def __contains__(self, vertex_id: object) -> bool:
        return vertex_id in self._vertices

    def position(self, vertex_id: str) -> tuple[float, float]:
        return self._vertices[vertex_id].position

    def neighbors(self, vertex_id: str) -> tuple[str, ...]:
        return self._adjacency[vertex_id]

    def degree(self, vertex_id: str) -> int:
        return len(self._adjacency[vertex_id])

    def is_adjacent(self, a: str, b: str) -> bool:
        return b in self._adjacency[a]

    def edge_between(self, a: str, b: str) -> Edge | None:
        for edge in self._edges:
            if edge.connects(a, b):
                return edge
        return None

    def bfs_distances(
        self, source: str, blocked: Iterable[str] = ()
    ) -> dict[str, int]:
        """Distances en nombre d'arêtes depuis `source`, sommets bloqués exclus."""
        blocked_set = set(blocked)
        blocked_set.discard(source)
        distances: dict[str, int] = {source: 0}
        queue: deque[str] = deque([source])
        while queue:
            current = queue.popleft()
            for neighbor in self._adjacency[current]:
                if neighbor in distances or neighbor in blocked_set:
                    continue
                distances[neighbor] = distances[current] + 1
                queue.append(neighbor)
        return distances

    def shortest_path(
        self, source: str, target: str, blocked: Iterable[str] = ()
    ) -> list[str] | None:
        """Plus court chemin (BFS) de `source` à `target`, ou None si inaccessible."""
        if source == target:
            return [source]
        blocked_set = set(blocked)
        blocked_set.discard(source)
        blocked_set.discard(target)
        previous: dict[str, str] = {}
        distances: dict[str, int] = {source: 0}
        queue: deque[str] = deque([source])
        while queue:
            current = queue.popleft()
            for neighbor in self._adjacency[current]:
                if neighbor in distances or neighbor in blocked_set:
                    continue
                distances[neighbor] = distances[current] + 1
                previous[neighbor] = current
                if neighbor == target:
                    path = [target]
                    while path[-1] != source:
                        path.append(previous[path[-1]])
                    return path[::-1]
                queue.append(neighbor)
        return None

    def is_connected(self) -> bool:
        if not self._vertices:
            return True
        return len(self.bfs_distances(next(iter(self._vertices)))) == len(self._vertices)

    def validate(self) -> list[str]:
        """Contrôles d'intégrité ; retourne la liste des anomalies détectées."""
        problems: list[str] = []
        if len(self._vertices) != len(self._adjacency):
            problems.append("adjacence incomplète")
        for vid in self._vertices:
            for neighbor in self._adjacency[vid]:
                if vid not in self._adjacency.get(neighbor, ()):
                    problems.append(f"arc non symétrique {vid}->{neighbor}")
        if not self.is_connected():
            problems.append("graphe non connexe")
        total_degree = sum(len(v) for v in self._adjacency.values())
        if total_degree != 2 * len(self._edges):
            problems.append("somme des degrés incohérente")
        counts: dict[str, int] = {}
        for edge in self._edges:
            counts[edge.primitive] = counts.get(edge.primitive, 0) + 1
        for primitive, expected in PRIMITIVE_EDGE_COUNTS.items():
            if counts.get(primitive, 0) != expected:
                problems.append(
                    f"primitive {primitive}: {counts.get(primitive, 0)} arêtes (attendu {expected})"
                )
        return problems


def build_default_graph() -> Graph:
    """Construit le graphe officiel du plateau (21 sommets, 36 arêtes)."""
    return Graph(VERTEX_POSITIONS, EDGE_PRIMITIVES)
