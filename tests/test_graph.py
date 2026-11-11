"""Tests de structure et de cohérence du graphe du plateau."""

from __future__ import annotations

import pytest

from core.board_geometry import (
    ARC_CIRCLES,
    CENTRAL_CIRCLE,
    HORIZONTAL_LINE,
    OUTER_ELLIPSE,
    VERTICAL_LINE,
    ellipse_norm,
)
from core.constants import CENTER
from core.graph import (
    EDGE_PRIMITIVES,
    PRIMITIVE_EDGE_COUNTS,
    VERTEX_POSITIONS,
    build_default_graph,
)


@pytest.fixture(scope="module")
def graph():
    return build_default_graph()


def test_vertex_and_edge_counts(graph):
    assert len(graph) == 21
    assert len(graph.edges) == 36


def test_identifiers_unique_and_positions_distinct(graph):
    assert len(set(graph.vertices)) == 21
    positions = [graph.position(v) for v in graph]
    assert len(set(positions)) == 21


def test_adjacency_symmetric(graph):
    for vid in graph:
        for neighbor in graph.neighbors(vid):
            assert vid in graph.neighbors(neighbor), f"{vid}-{neighbor} non symétrique"


def test_no_duplicate_edges():
    keys = {tuple(sorted((u, v))) for u, v, _ in EDGE_PRIMITIVES}
    assert len(keys) == len(EDGE_PRIMITIVES)


def test_degrees(graph):
    degree_three = {"T", "B", "L", "R", "EA1", "EA2", "EA6", "EA7", "EALt", "EALb", "EARt", "EARb"}
    degree_four = {"CENTER", "J1", "J2", "VCt", "VCb", "HCl", "HCr", "HAL", "HAR"}
    for vid in degree_three:
        assert graph.degree(vid) == 3, vid
    for vid in degree_four:
        assert graph.degree(vid) == 4, vid
    assert sum(graph.degree(v) for v in graph) == 72


def test_graph_connected(graph):
    assert graph.is_connected()
    distances = graph.bfs_distances(CENTER)
    assert len(distances) == 21
    assert distances[CENTER] == 0


def test_center_identified(graph):
    assert graph.center == CENTER
    assert graph.position(CENTER) == (352.0, 406.5)
    assert set(graph.neighbors(CENTER)) == {"VCt", "VCb", "HCl", "HCr"}


def test_primitive_edges(graph):
    counts = {}
    for edge in graph.edges:
        counts[edge.primitive] = counts.get(edge.primitive, 0) + 1
    assert counts == PRIMITIVE_EDGE_COUNTS


def test_validate_reports_no_problem(graph):
    assert graph.validate() == []


def test_bfs_distances(graph):
    distances = graph.bfs_distances("T")
    assert distances["T"] == 0
    assert distances["J1"] == 1
    assert distances["CENTER"] == 3
    assert distances["HCr"] == 3


def test_shortest_path(graph):
    path = graph.shortest_path("CENTER", "T")
    assert path is not None
    assert path[0] == CENTER and path[-1] == "T"
    for a, b in zip(path, path[1:]):
        assert graph.is_adjacent(a, b)


def test_shortest_path_respects_blocked_vertices(graph):
    free = graph.shortest_path("EA2", "EA7")
    assert free is not None
    blocked = {v for v in graph if v not in ("EA2", "EA7")}
    assert graph.shortest_path("EA2", "EA7", blocked=blocked) is None


def test_left_right_symmetry(graph):
    mirror = {
        "EA1": "EA2", "EA2": "EA1", "EARt": "EALt", "EALt": "EARt",
        "EARb": "EALb", "EALb": "EARb", "R": "L", "L": "R",
        "HAR": "HAL", "HAL": "HAR", "EA7": "EA6", "EA6": "EA7",
        "HCr": "HCl", "HCl": "HCr",
    }
    for vid in ("T", "B", "CENTER", "J1", "J2", "VCt", "VCb"):
        mirror[vid] = vid
    for u, v, _ in EDGE_PRIMITIVES:
        assert graph.edge_between(mirror[u], mirror[v]) is not None, f"{u}-{v}"


def test_top_bottom_symmetry(graph):
    mirror = {
        "T": "B", "B": "T", "EA2": "EA6", "EA6": "EA2", "EA1": "EA7",
        "EA7": "EA1", "EALt": "EALb", "EALb": "EALt", "EARt": "EARb",
        "EARb": "EARt", "J1": "J2", "J2": "J1", "VCt": "VCb", "VCb": "VCt",
    }
    for vid in ("L", "R", "CENTER", "HAL", "HAR", "HCl", "HCr"):
        mirror[vid] = vid
    for u, v, _ in EDGE_PRIMITIVES:
        assert graph.edge_between(mirror[u], mirror[v]) is not None, f"{u}-{v}"


def test_vertices_lie_on_their_primitives(graph):
    on_ellipse = ("T", "B", "L", "R", "EA1", "EA2", "EA6", "EA7", "EALt", "EALb", "EARt", "EARb")
    for vid in on_ellipse:
        x, y = graph.position(vid)
        assert abs(ellipse_norm(x, y) - 1.0) * min(OUTER_ELLIPSE.a, OUTER_ELLIPSE.b) < 2.0

    for vid in ("T", "J1", "VCt", "CENTER", "VCb", "J2", "B"):
        assert abs(graph.position(vid)[0] - VERTICAL_LINE.x1) < 0.01

    for vid in ("L", "HAL", "HCl", "CENTER", "HCr", "HAR", "R"):
        assert abs(graph.position(vid)[1] - HORIZONTAL_LINE.y1) < 0.01

    for vid in ("VCt", "VCb", "HCl", "HCr"):
        x, y = graph.position(vid)
        distance = ((x - CENTRAL_CIRCLE.cx) ** 2 + (y - CENTRAL_CIRCLE.cy) ** 2) ** 0.5
        assert abs(distance - CENTRAL_CIRCLE.r) < 0.6

    arc_ends = {
        "A1": ("J1", "EA1"), "A2": ("J1", "EA2"), "A6": ("J2", "EA6"), "A7": ("J2", "EA7"),
        "ALU": ("EALt", "HAL"), "ALL": ("HAL", "EALb"),
        "ARU": ("EARt", "HAR"), "ARL": ("HAR", "EARb"),
    }
    for arc, (a, b) in arc_ends.items():
        circle = ARC_CIRCLES[arc]
        for vid in (a, b):
            x, y = graph.position(vid)
            distance = ((x - circle.cx) ** 2 + (y - circle.cy) ** 2) ** 0.5
            assert abs(distance - circle.r) < 1.5, (arc, vid)


def test_coordinates_within_board(graph):
    for vid in graph:
        x, y = graph.position(vid)
        assert 0 <= x <= 689 and 0 <= y <= 796


def test_vertex_positions_match_graph_module():
    assert set(VERTEX_POSITIONS) == set(build_default_graph().vertices)
