"""Table rétrograde exacte : chaque position est GAIN POLICE, GAIN VOLEUR ou nulle."""

from __future__ import annotations

import time
from collections import deque

from ai.evaluation import evaluate
from ai.minimax import MoveEvaluation, SearchResult
from core.constants import CENTER, POLICE_WIN_SCORE, THIEF_WIN_SCORE, Team
from core.game_rules import apply_move, police_legal_moves
from core.game_state import GameState
from core.graph import Graph
from core.ruleset import DEFAULT_RULES, RuleSet

DRAW = _DRAW_VALUE = 500_000
LOSE = 1_000_000
WIN_MARK, LOSE_MARK = 1, 2


class SolvedGame:
    """Valeurs exactes + politique policière, calculées une seule fois."""

    def __init__(self, graph: Graph, rules: RuleSet = DEFAULT_RULES) -> None:
        self.graph, self.rules = graph, rules
        self.cooldown = max(0, rules.return_cooldown)
        self.contest = rules.center_contestable
        vertices = tuple(sorted(graph))
        self.n = n = len(vertices)
        self.ix = ix = {v: i for i, v in enumerate(vertices)}
        self.adj = adj = tuple(tuple(ix[w] for w in graph.neighbors(v)) for v in vertices)
        center = ix[CENTER]
        total = 2 * n**4
        mark, dw, dl = bytearray(total), [0] * total, [0] * total
        children: list[tuple[int, ...] | None] = [None] * total
        preds: dict[int, list[int]] = {}
        wins, losses = [], []
        valid = 0

        def sid(t, a, b, c, turn):
            return ((((t * n + a) * n + b) * n + c) << 1) | turn

        for t in range(n):
            others = [i for i in range(n) if i != t]
            for i in range(n - 1):
                for j in range(i + 1, n - 1):
                    for k in range(j + 1, n - 1):
                        p0, p1, p2 = others[i], others[j], others[k]
                        cops = (p0, p1, p2)
                        st, sp = sid(t, p0, p1, p2, 0), sid(t, p0, p1, p2, 1)
                        valid += 2
                        if all(x in cops for x in adj[t]):
                            mark[st] = mark[sp] = WIN_MARK
                            wins += [st, sp]
                            continue
                        if center in adj[t] and center not in cops:
                            mark[st], dl[st] = LOSE_MARK, 1
                            losses.append(st)
                        children[st] = tuple(
                            sid(x, p0, p1, p2, 1) for x in adj[t]
                            if x not in cops and x != center
                        )
                        police_kids = []
                        for cop in cops:
                            for x in adj[cop]:
                                if x == t or x in cops or (x == center and not self.contest):
                                    continue
                                nps = tuple(sorted(y if y != cop else x for y in cops))
                                y = sid(t, *nps, 0)
                                police_kids.append(y)
                                preds.setdefault(y, []).append(sp)
                        children[sp] = tuple(police_kids)
                        for y in children[st]:
                            preds.setdefault(y, []).append(st)

        def attract(seeds, dist, direct):
            mark_value = LOSE_MARK if direct == 0 else WIN_MARK
            queue = deque()
            for seed in seeds:
                mark[seed] = mark_value
                dist[seed] = 1 if direct == 0 else 0
                queue.append(seed)
            left = {s: len(ch) for s, ch in enumerate(children)
                    if ch is not None and s & 1 != direct and not mark[s]}
            worst: dict[int, int] = {}
            while queue:
                s = queue.popleft()
                for parent in preds.get(s, ()):
                    if mark[parent]:
                        continue
                    if parent & 1 == direct:
                        mark[parent], dist[parent] = mark_value, dist[s] + 1
                        queue.append(parent)
                    else:
                        left[parent] -= 1
                        worst[parent] = max(worst.get(parent, 0), dist[s])
                        if left[parent] == 0:
                            mark[parent], dist[parent] = mark_value, worst[parent] + 1
                            queue.append(parent)

        attract(losses, dl, 0)
        attract(wins, dw, 1)
        self.mark, self.dw, self.dl = mark, dw, dl
        self.node_count = self.valid_count = valid
        self.win_states = mark.count(WIN_MARK)
        self.lose_states = mark.count(LOSE_MARK)
        self.draw_states = valid - self.win_states - self.lose_states
        self._memo: dict[int, int] = {}
        self.memo_hits = 0

    def sid_of(self, state: GameState) -> int:
        p = sorted(self.ix[v] for v in state.police)
        turn = 1 if state.turn is Team.POLICE else 0
        return ((((self.ix[state.thief] * self.n + p[0]) * self.n + p[1])
                 * self.n + p[2]) << 1) | turn

    def _table(self, sid: int) -> int:
        m = self.mark[sid]
        return self.dw[sid] if m == WIN_MARK else (
            LOSE - self.dl[sid] if m == LOSE_MARK else DRAW)

    def value(self, state: GameState, ply: int) -> int:
        return self.value_sid(self.sid_of(state), min(max(0, ply), self.cooldown))

    def value_sid(self, sid: int, k: int) -> int:
        if k >= self.cooldown:
            return self._table(sid)
        key = sid * (self.cooldown + 1) + k
        if key in self._memo:
            self.memo_hits += 1
            return self._memo[key]
        code, turn = sid >> 1, sid & 1
        code, p2 = divmod(code, self.n)
        code, p1 = divmod(code, self.n)
        t, p0 = divmod(code, self.n)
        cops, center = (p0, p1, p2), self.ix[CENTER]
        if all(x in cops or x == center for x in self.adj[t]):
            value = 0
        elif turn == 0:
            value = max(
                (self.value_sid(((x * self.n + p0) * self.n + p1) * self.n + p2 << 1 | 1,
                                k + 1) for x in self.adj[t]
                 if x not in cops and x != center),
                default=-1,
            )
        else:
            values = []
            for cop in cops:
                for x in self.adj[cop]:
                    if x == t or x in cops or (x == center and not self.contest):
                        continue
                    nps = tuple(sorted(y if y != cop else x for y in cops))
                    values.append(self.value_sid(
                        ((t * self.n + nps[0]) * self.n + nps[1]) * self.n + nps[2] << 1,
                        k + 1))
            value = min(values) if values else DRAW
        self._memo[key] = value
        return value

    @staticmethod
    def is_win(value: int) -> bool:
        return value < DRAW

    @staticmethod
    def is_loss(value: int) -> bool:
        return value > DRAW

    @staticmethod
    def distance(value: int) -> int:
        return value if value < DRAW else (LOSE - value if value > DRAW else 0)

    def map_score(self, value: int, heuristic: int) -> int:
        if value < DRAW:
            return POLICE_WIN_SCORE - value
        if value > DRAW:
            return THIEF_WIN_SCORE + (LOSE - value)
        return max(THIEF_WIN_SCORE + 1000, min(POLICE_WIN_SCORE - 1000, heuristic))

    def best_move(self, state, ply, history_counts=None, repetition_limit=0):
        moves = police_legal_moves(self.graph, state, self.rules)
        if not moves:
            return None, DRAW, []
        k = min(ply + 1, self.cooldown)
        entries = []
        for move in moves:
            child = apply_move(self.graph, state, move, self.rules, ply)
            value = self.value_sid(self.sid_of(child), k)
            heuristic = evaluate(self.graph, child, ply + 1, self.rules)
            repeat = history_counts.get(child.position_key(), 0) if history_counts else 0
            if (repeat and repetition_limit > 0 and repeat + 1 >= repetition_limit
                    and value != 0 and value < DRAW):
                value = DRAW
            entries.append(((value, repeat, -heuristic), move, value, heuristic))
        entries.sort(key=lambda item: item[0])
        return entries[0][1], entries[0][2], [(m, v, h) for _, m, v, h in entries]


_SOLVERS: dict[tuple, SolvedGame] = {}


def solved_game(graph: Graph, rules: RuleSet = DEFAULT_RULES) -> SolvedGame:
    """Retourne (et mémorise) le jeu résolu pour ce graphe et ces règles."""
    key = (tuple(sorted((min(e.u, e.v), max(e.v, e.u)) for e in graph.edges)),
           rules.return_cooldown, rules.center_contestable)
    if key not in _SOLVERS:
        _SOLVERS[key] = SolvedGame(graph, rules)
    return _SOLVERS[key]


class PoliceSolverEngine:
    """Moteur exact de la POLICE ; interface compatible `SearchEngine`."""

    def __init__(self, graph: Graph) -> None:
        self.graph = graph
        self.history: tuple[GameState, ...] = ()
        self.repetition_limit = 0

    def set_context(self, history=(), repetition_limit=0) -> None:
        self.history, self.repetition_limit = tuple(history), int(repetition_limit)

    def search(self, state, config=None, ply=0) -> SearchResult:
        start = time.perf_counter()
        rules = config.rules if config is not None else DEFAULT_RULES
        if state.turn is not Team.POLICE:
            raise ValueError("le solveur POLICE ne traite que les tours de la police")
        solver = solved_game(self.graph, rules)
        counts = None
        if self.history and self.repetition_limit > 0:
            counts = {}
            for previous in self.history:
                counts[previous.position_key()] = counts.get(previous.position_key(), 0) + 1
        hits = solver.memo_hits
        move, value, entries = solver.best_move(state, ply, counts, self.repetition_limit)
        if move is None:
            return SearchResult(None, evaluate(self.graph, state, ply, rules), 0, True,
                                solver.node_count, 0, solver.memo_hits - hits,
                                time.perf_counter() - start)
        return SearchResult(
            move, solver.map_score(value, next(h for m, _, h in entries if m == move)),
            solver.distance(value), True, solver.node_count, 0,
            solver.memo_hits - hits, time.perf_counter() - start,
            tuple(MoveEvaluation(m, solver.map_score(v, h)) for m, v, h in entries),
        )
