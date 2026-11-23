"""Table rétrograde exacte utilisée comme évaluation feuille par le minimax policier."""

from __future__ import annotations

from collections import deque

from core.constants import CENTER, Team
from core.graph import Graph
from core.ruleset import DEFAULT_RULES, RuleSet

_WIN, _LOSE = 1, 2
_DRAW = 500_000
_LOSE_BASE = 1_000_000

_THIEF, _POLICE = 0, 1


class Board:
    """Encodage entier des positions : (voleur, p0, p1, p2, camp)."""

    __slots__ = ("adj", "center", "index", "size")

    def __init__(self, graph: Graph) -> None:
        vertices = tuple(sorted(graph))
        self.index = {vertex: rank for rank, vertex in enumerate(vertices)}
        self.size = len(vertices)
        self.center = self.index[CENTER]
        self.adj = tuple(
            tuple(self.index[neighbor] for neighbor in graph.neighbors(vertex))
            for vertex in vertices
        )

    def sid(self, thief: int, p0: int, p1: int, p2: int, turn: int) -> int:
        size = self.size
        return ((((thief * size + p0) * size + p1) * size + p2) << 1) | turn

    def decode(self, sid: int) -> tuple[int, int, int, int, int]:
        turn = sid & 1
        code = sid >> 1
        code, p2 = divmod(code, self.size)
        code, p1 = divmod(code, self.size)
        thief, p0 = divmod(code, self.size)
        return thief, p0, p1, p2, turn


class ExactTable:
    """Valeur exacte de chaque position canonique + distance de capture."""

    def __init__(self, graph: Graph, rules: RuleSet) -> None:
        self.board = Board(graph)
        self.cooldown = max(0, rules.return_cooldown)
        self.contestable = rules.center_contestable
        self.memo: dict[int, int] = {}
        self.stride = self.cooldown + 1
        self._build()
        self._retrograde()

    def _build(self) -> None:
        board = self.board
        size, adj, center = board.size, board.adj, board.center
        total = size**4 << 1
        mark = bytearray(total)
        dw, dl = [0] * total, [0] * total
        children: list[tuple[int, ...] | None] = [None] * total
        predecessors: dict[int, list[int]] = {}
        win_seeds: list[int] = []
        lose_seeds: list[int] = []

        add_predecessor = predecessors.setdefault
        for thief in range(size):
            others = [vertex for vertex in range(size) if vertex != thief]
            neighbors = adj[thief]
            base = thief * size
            for i, p0 in enumerate(others):
                base0 = (base + p0) * size
                for j in range(i + 1, size - 1):
                    p1 = others[j]
                    base1 = (base0 + p1) * size
                    for k in range(j + 1, size - 1):
                        p2 = others[k]
                        police = (p0, p1, p2)
                        thief_sid = (base1 + p2) << 1
                        police_sid = thief_sid | 1

                        if all(neighbor in police for neighbor in neighbors):
                            for sid in (thief_sid, police_sid):
                                mark[sid] = _WIN
                                win_seeds.append(sid)
                            continue

                        if center in neighbors and center not in police:
                            mark[thief_sid] = _LOSE
                            dl[thief_sid] = 1
                            lose_seeds.append(thief_sid)

                        kids = []
                        for dst in neighbors:
                            if dst in police or dst == center:
                                continue
                            child = ((((dst * size + p0) * size + p1) * size + p2) << 1) | 1
                            kids.append(child)
                            add_predecessor(child, []).append(thief_sid)
                        children[thief_sid] = tuple(kids)

                        kids = []
                        for index, cop in enumerate(police):
                            for dst in adj[cop]:
                                if dst == thief or dst in police:
                                    continue
                                if dst == center and not self.contestable:
                                    continue
                                if index == 0:
                                    if dst < p1:
                                        m0, m1, m2 = dst, p1, p2
                                    elif dst < p2:
                                        m0, m1, m2 = p1, dst, p2
                                    else:
                                        m0, m1, m2 = p1, p2, dst
                                elif index == 1:
                                    if dst < p0:
                                        m0, m1, m2 = dst, p0, p2
                                    elif dst < p2:
                                        m0, m1, m2 = p0, dst, p2
                                    else:
                                        m0, m1, m2 = p0, p2, dst
                                else:
                                    if dst < p0:
                                        m0, m1, m2 = dst, p0, p1
                                    elif dst < p1:
                                        m0, m1, m2 = p0, dst, p1
                                    else:
                                        m0, m1, m2 = p0, p1, dst
                                child = (((thief * size + m0) * size + m1) * size + m2) << 1
                                kids.append(child)
                                add_predecessor(child, []).append(police_sid)
                        children[police_sid] = tuple(kids)

        self.mark = mark
        self.dw = dw
        self.dl = dl
        self.children = children
        self.predecessors = predecessors
        self.win_seeds = win_seeds
        self.lose_seeds = lose_seeds

    def _attractor(
        self,
        seeds: list[int],
        flag: int,
        parent_flag: int,
        distance: list[int],
    ) -> None:
        mark, children, predecessors = self.mark, self.children, self.predecessors
        remaining = {
            sid: len(children[sid])
            for sid in predecessors
            if children[sid] is not None and not mark[sid] and (sid & 1) != parent_flag
        }
        maximum: dict[int, int] = {}
        queue = deque(seeds)
        while queue:
            sid = queue.popleft()
            value = distance[sid]
            for parent in predecessors.get(sid, ()):
                if mark[parent]:
                    continue
                if (parent & 1) == parent_flag:
                    mark[parent] = flag
                    distance[parent] = value + 1
                    queue.append(parent)
                    continue
                left = remaining.get(parent)
                if left is None:
                    continue
                left -= 1
                remaining[parent] = left
                if value > maximum.get(parent, 0):
                    maximum[parent] = value
                if left == 0:
                    mark[parent] = flag
                    distance[parent] = maximum[parent] + 1
                    queue.append(parent)

    def _retrograde(self) -> None:
        self._attractor(self.lose_seeds, _LOSE, _THIEF, self.dl)
        self._attractor(self.win_seeds, _WIN, _POLICE, self.dw)
        self.children = None
        self.predecessors = None

    def value_sid(self, sid: int, k: int) -> int:
        """Valeur exacte ; `k` = min(ply, cooldown)."""
        if k >= self.cooldown:
            return self._table_value(sid)
        key = sid * self.stride + k
        cached = self.memo.get(key)
        if cached is not None:
            return cached

        board = self.board
        thief, p0, p1, p2, turn = board.decode(sid)
        police = (p0, p1, p2)
        neighbors = board.adj[thief]
        if all(dst in police or dst == board.center for dst in neighbors):
            value = 0
        elif turn == _THIEF:
            value = max(
                (
                    self.value_sid(board.sid(dst, p0, p1, p2, _POLICE), k + 1)
                    for dst in neighbors
                    if dst not in police and dst != board.center
                ),
                default=_DRAW,
            )
        else:
            candidates = []
            for index, cop in enumerate(police):
                for dst in board.adj[cop]:
                    if dst == thief or dst in police:
                        continue
                    if dst == board.center and not self.contestable:
                        continue
                    if index == 0:
                        if dst < p1:
                            moved = (dst, p1, p2)
                        elif dst < p2:
                            moved = (p1, dst, p2)
                        else:
                            moved = (p1, p2, dst)
                    elif index == 1:
                        if dst < p0:
                            moved = (dst, p0, p2)
                        elif dst < p2:
                            moved = (p0, dst, p2)
                        else:
                            moved = (p0, p2, dst)
                    else:
                        if dst < p0:
                            moved = (dst, p0, p1)
                        elif dst < p1:
                            moved = (p0, dst, p1)
                        else:
                            moved = (p0, p1, dst)
                    candidates.append(
                        self.value_sid(board.sid(thief, *moved, _THIEF), k + 1)
                    )
            value = min(candidates, default=_DRAW)
        self.memo[key] = value
        return value

    def _table_value(self, sid: int) -> int:
        flag = self.mark[sid]
        if flag == _WIN:
            return self.dw[sid]
        if flag == _LOSE:
            return _LOSE_BASE - self.dl[sid]
        return _DRAW

    def sid_of(self, state) -> int:
        board = self.board
        p0, p1, p2 = sorted(board.index[vertex] for vertex in state.police)
        turn = _POLICE if state.turn is Team.POLICE else _THIEF
        return board.sid(board.index[state.thief], p0, p1, p2, turn)


_TABLES: dict[tuple, ExactTable] = {}


def table_for(graph: Graph, rules: RuleSet) -> ExactTable:
    key = (tuple(sorted((edge.u, edge.v) for edge in graph.edges)), rules)
    table = _TABLES.get(key)
    if table is None:
        table = _TABLES[key] = ExactTable(graph, rules)
    return table


_Board = Board
_Table = ExactTable
_table_for = table_for

__all__ = ["Board", "ExactTable", "table_for", "DRAW", "LOSE_BASE"]

DRAW = _DRAW
LOSE_BASE = _LOSE_BASE
