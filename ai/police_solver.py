"""Solveur exact pour la POLICE : analyse rétrograde du jeu complet.

Contrairement au Minimax à profondeur limitée de `ai/minimax.py` (qui reste l'IA du
VOLEUR, inchangée), ce module **résout entièrement** le jeu sur son espace d'états
fini (21 sommets, 3 policiers, 1 voleur, 2 camps, cooldown du centre) :

- la table principale est calculée par analyse rétrograde (attracteurs WIN / LOSE +
  distances de capture) pour la phase « centre ouvert » (retour du voleur autorisé) ;
- les premiers demi-coups (cooldown du centre, où le retour au centre est interdit)
  sont évalués par récursion mémorisée vers cette table : le cooldown avance d'un
  demi-coup par demi-coup, la récursion est donc bien fondée ;
- la politique policière choisit toujours un coup qui reste dans la région gagnante
  en minimisant la distance de capture (et évite les nulles par répétition).

Conséquence : dès que la position courante appartient à la région gagnante de la
POLICE, celle-ci **rattrape le voleur quel que soit son jeu**. Si la position est
nulle ou perdue (possible seulement avec des règles dégénérées, par exemple
`center_contestable=False`), la police joue le coup qui résiste le plus longtemps.

Le VOLEUR n'est pas modifié : il continue d'utiliser `ai/minimax.py`.
"""

from __future__ import annotations

import hashlib
import pickle
import tempfile
import threading
import time
from collections import deque
from pathlib import Path

from ai.evaluation import evaluate
from ai.minimax import MoveEvaluation, SearchResult
from core.constants import CENTER, POLICE_WIN_SCORE, THIEF_WIN_SCORE, Team
from core.game_rules import apply_move, police_legal_moves
from core.game_state import GameState, Move
from core.graph import Graph
from core.ruleset import DEFAULT_RULES, RuleSet

_WIN = 1
_LOSE = 2

_THIEF_TURN = 0
_POLICE_TURN = 1

_DRAW_VALUE = 500_000
_LOSE_BASE = 1_000_000

_CACHE_VERSION = 1


class _Board:
    """Encodage compact des positions (entiers) pour l'analyse rétrograde."""

    __slots__ = ("vertices", "index", "adjacency", "center", "size")

    def __init__(self, graph: Graph) -> None:
        self.vertices = tuple(sorted(graph.vertices))
        self.index = {vertex: rank for rank, vertex in enumerate(self.vertices)}
        self.adjacency = tuple(
            tuple(self.index[neighbor] for neighbor in graph.neighbors(vertex))
            for vertex in self.vertices
        )
        self.center = self.index[CENTER]
        self.size = len(self.vertices)

    def sid(self, thief: int, p0: int, p1: int, p2: int, turn: int) -> int:
        return ((((thief * self.size + p0) * self.size + p1) * self.size + p2) << 1) | turn

    def decode(self, sid: int) -> tuple[int, int, int, int, int]:
        turn = sid & 1
        code = sid >> 1
        code, p2 = divmod(code, self.size)
        code, p1 = divmod(code, self.size)
        thief, p0 = divmod(code, self.size)
        return thief, p0, p1, p2, turn


class _SolvedGame:
    """Valeur exacte de chaque position + politique optimale de la POLICE."""

    def __init__(self, graph: Graph, rules: RuleSet) -> None:
        self.graph = graph
        self.rules = rules
        self.board = _Board(graph)
        self.cooldown = max(0, rules.return_cooldown)
        self.center_contestable = rules.center_contestable
        self._memo: dict[int, int] = {}
        self._memo_stride = self.cooldown + 1
        self.memo_hits = 0
        self.node_count = 0
        self.win_states = 0
        self.draw_states = 0
        self.lose_states = 0
        self._solve()

    # ------------------------------------------------------------------ résolution

    def _cache_key(self) -> tuple:
        edges = tuple(sorted((min(e.u, e.v), max(e.u, e.v)) for e in self.graph.edges))
        return (
            _CACHE_VERSION,
            edges,
            self.rules.return_cooldown,
            self.rules.center_contestable,
        )

    def _solve(self) -> None:
        key = self._cache_key()
        cached = _load_cache(key)
        if cached is not None:
            (
                self.mark,
                self.dw,
                self.dl,
                self.blocked,
                self.center_win,
                stats,
            ) = cached
            (
                self.node_count,
                self.win_states,
                self.draw_states,
                self.lose_states,
            ) = stats
            self.valid_count = self.node_count
            return
        self._build()
        self._retrograde()
        self._count_stats()
        _store_cache(
            key,
            (
                self.mark,
                self.dw,
                self.dl,
                self.blocked,
                self.center_win,
                (
                    self.node_count,
                    self.win_states,
                    self.draw_states,
                    self.lose_states,
                ),
            ),
        )

    def _build(self) -> None:
        board = self.board
        size = board.size
        total = (size ** 4) << 1
        adjacency = board.adjacency
        center = board.center
        contestable = self.center_contestable

        self.mark = bytearray(total)
        self.blocked = bytearray(total)
        self.center_win = bytearray(total)
        self.dw = [0] * total
        self.dl = [0] * total
        children: list[tuple[int, ...] | None] = [None] * total
        predecessors: dict[int, list[int]] = {}
        win_seeds: list[int] = []
        lose_seeds: list[int] = []
        valid_count = 0

        sid = board.sid
        for thief in range(size):
            others = [vertex for vertex in range(size) if vertex != thief]
            thief_neighbors = adjacency[thief]
            for i in range(size - 1):
                p0 = others[i]
                for j in range(i + 1, size - 1):
                    p1 = others[j]
                    for k in range(j + 1, size - 1):
                        p2 = others[k]
                        is_blocked = all(
                            neighbor == p0 or neighbor == p1 or neighbor == p2
                            for neighbor in thief_neighbors
                        )

                        valid_count += 2

                        thief_sid = sid(thief, p0, p1, p2, _THIEF_TURN)
                        if is_blocked:
                            self.blocked[thief_sid] = 1
                            win_seeds.append(thief_sid)
                        else:
                            if (
                                center in thief_neighbors
                                and center != p0
                                and center != p1
                                and center != p2
                            ):
                                self.center_win[thief_sid] = 1
                                lose_seeds.append(thief_sid)
                            kids: list[int] = []
                            for neighbor in thief_neighbors:
                                if neighbor == p0 or neighbor == p1 or neighbor == p2:
                                    continue
                                if neighbor == center:
                                    continue
                                child = sid(neighbor, p0, p1, p2, _POLICE_TURN)
                                kids.append(child)
                                predecessors.setdefault(child, []).append(thief_sid)
                            children[thief_sid] = tuple(kids)

                        police_sid = sid(thief, p0, p1, p2, _POLICE_TURN)
                        if is_blocked:
                            self.blocked[police_sid] = 1
                            win_seeds.append(police_sid)
                        else:
                            kids = []
                            for cop in (p0, p1, p2):
                                for neighbor in adjacency[cop]:
                                    if (
                                        neighbor == thief
                                        or neighbor == p0
                                        or neighbor == p1
                                        or neighbor == p2
                                    ):
                                        continue
                                    if neighbor == center and not contestable:
                                        continue
                                    if cop == p0:
                                        if neighbor < p1:
                                            np0, np1, np2 = neighbor, p1, p2
                                        elif neighbor < p2:
                                            np0, np1, np2 = p1, neighbor, p2
                                        else:
                                            np0, np1, np2 = p1, p2, neighbor
                                    elif cop == p1:
                                        if neighbor < p0:
                                            np0, np1, np2 = neighbor, p0, p2
                                        elif neighbor < p2:
                                            np0, np1, np2 = p0, neighbor, p2
                                        else:
                                            np0, np1, np2 = p0, p2, neighbor
                                    else:
                                        if neighbor < p0:
                                            np0, np1, np2 = neighbor, p0, p1
                                        elif neighbor < p1:
                                            np0, np1, np2 = p0, neighbor, p1
                                        else:
                                            np0, np1, np2 = p0, p1, neighbor
                                    child = sid(thief, np0, np1, np2, _THIEF_TURN)
                                    kids.append(child)
                                    predecessors.setdefault(child, []).append(police_sid)
                            children[police_sid] = tuple(kids)

        self.children = children
        self.predecessors = predecessors
        self._win_seeds = win_seeds
        self._lose_seeds = lose_seeds
        self.valid_count = valid_count

    def _retrograde(self) -> None:
        mark, dw, dl = self.mark, self.dw, self.dl
        children = self.children
        predecessors = self.predecessors

        # --- Attracteur LOSE : le voleur force le retour au centre. -----------------
        queue: deque[int] = deque()
        for seed in self._lose_seeds:
            mark[seed] = _LOSE
            dl[seed] = 1
            queue.append(seed)
        remaining: dict[int, int] = {}
        max_dl: dict[int, int] = {}
        for state_sid, kids in enumerate(children):
            if kids is None or mark[state_sid]:
                continue
            if state_sid & 1 == _POLICE_TURN:
                remaining[state_sid] = len(kids)
        while queue:
            state = queue.popleft()
            distance = dl[state]
            for parent in predecessors.get(state, ()):
                if mark[parent]:
                    continue
                if parent & 1 == _THIEF_TURN:
                    mark[parent] = _LOSE
                    dl[parent] = distance + 1
                    queue.append(parent)
                else:
                    left = remaining.get(parent)
                    if left is None:
                        continue
                    left -= 1
                    remaining[parent] = left
                    if distance > max_dl.get(parent, 0):
                        max_dl[parent] = distance
                    if left == 0:
                        mark[parent] = _LOSE
                        dl[parent] = max_dl[parent] + 1
                        queue.append(parent)

        # --- Attracteur WIN : la police bloque le voleur (sur le complément). -------
        queue = deque()
        for seed in self._win_seeds:
            mark[seed] = _WIN
            dw[seed] = 0
            queue.append(seed)
        remaining = {}
        max_dw: dict[int, int] = {}
        for state_sid, kids in enumerate(children):
            if kids is None or mark[state_sid]:
                continue
            remaining[state_sid] = len(kids)
        while queue:
            state = queue.popleft()
            distance = dw[state]
            for parent in predecessors.get(state, ()):
                if mark[parent]:
                    continue
                if parent & 1 == _POLICE_TURN:
                    mark[parent] = _WIN
                    dw[parent] = distance + 1
                    queue.append(parent)
                else:
                    left = remaining.get(parent)
                    if left is None:
                        continue
                    left -= 1
                    remaining[parent] = left
                    if distance > max_dw.get(parent, 0):
                        max_dw[parent] = distance
                    if left == 0:
                        mark[parent] = _WIN
                        dw[parent] = max_dw[parent] + 1
                        queue.append(parent)

        self.children = None
        self.predecessors = None

    def _count_stats(self) -> None:
        wins = self.mark.count(_WIN)
        losses = self.mark.count(_LOSE)
        self.win_states = wins
        self.lose_states = losses
        self.draw_states = max(0, self.valid_count - wins - losses)
        self.node_count = self.valid_count

    # ------------------------------------------------------------------ valeurs

    def sid_of(self, state: GameState) -> int:
        board = self.board
        p0, p1, p2 = sorted(board.index[vertex] for vertex in state.police)
        turn = _POLICE_TURN if state.turn is Team.POLICE else _THIEF_TURN
        return board.sid(board.index[state.thief], p0, p1, p2, turn)

    def value(self, state: GameState, ply: int) -> int:
        k = min(max(0, ply), self.cooldown)
        return self.value_sid(self.sid_of(state), k)

    def value_sid(self, state_sid: int, k: int) -> int:
        if k >= self.cooldown:
            return self._table_value(state_sid)
        key = state_sid * self._memo_stride + k
        cached = self._memo.get(key)
        if cached is not None:
            self.memo_hits += 1
            return cached

        board = self.board
        thief, p0, p1, p2, turn = board.decode(state_sid)
        thief_neighbors = board.adjacency[thief]
        center = board.center

        is_blocked = True
        for neighbor in thief_neighbors:
            if neighbor == p0 or neighbor == p1 or neighbor == p2:
                continue
            if neighbor == center:
                continue
            is_blocked = False
            break

        if is_blocked:
            value = 0
        elif turn == _THIEF_TURN:
            best = -1
            for neighbor in thief_neighbors:
                if neighbor == p0 or neighbor == p1 or neighbor == p2:
                    continue
                if neighbor == center:
                    continue
                child = board.sid(neighbor, p0, p1, p2, _POLICE_TURN)
                candidate = self.value_sid(child, k + 1)
                if candidate > best:
                    best = candidate
            value = best
        else:
            best = None
            for cop in (p0, p1, p2):
                for neighbor in board.adjacency[cop]:
                    if (
                        neighbor == thief
                        or neighbor == p0
                        or neighbor == p1
                        or neighbor == p2
                    ):
                        continue
                    if neighbor == center and not self.center_contestable:
                        continue
                    if cop == p0:
                        if neighbor < p1:
                            np0, np1, np2 = neighbor, p1, p2
                        elif neighbor < p2:
                            np0, np1, np2 = p1, neighbor, p2
                        else:
                            np0, np1, np2 = p1, p2, neighbor
                    elif cop == p1:
                        if neighbor < p0:
                            np0, np1, np2 = neighbor, p0, p2
                        elif neighbor < p2:
                            np0, np1, np2 = p0, neighbor, p2
                        else:
                            np0, np1, np2 = p0, p2, neighbor
                    else:
                        if neighbor < p0:
                            np0, np1, np2 = neighbor, p0, p1
                        elif neighbor < p1:
                            np0, np1, np2 = p0, neighbor, p1
                        else:
                            np0, np1, np2 = p0, p1, neighbor
                    child = board.sid(thief, np0, np1, np2, _THIEF_TURN)
                    candidate = self.value_sid(child, k + 1)
                    if best is None or candidate < best:
                        best = candidate
            value = _DRAW_VALUE if best is None else best

        self._memo[key] = value
        return value

    def _table_value(self, state_sid: int) -> int:
        flag = self.mark[state_sid]
        if flag == _WIN:
            return self.dw[state_sid]
        if flag == _LOSE:
            return _LOSE_BASE - self.dl[state_sid]
        return _DRAW_VALUE

    @staticmethod
    def is_win(value: int) -> bool:
        return value < _DRAW_VALUE

    @staticmethod
    def is_loss(value: int) -> bool:
        return value > _DRAW_VALUE

    @staticmethod
    def distance(value: int) -> int:
        if value < _DRAW_VALUE:
            return value
        if value > _DRAW_VALUE:
            return _LOSE_BASE - value
        return 0

    # ------------------------------------------------------------------ politique

    def best_move(
        self,
        state: GameState,
        ply: int,
        history_counts: dict[tuple, int] | None = None,
        repetition_limit: int = 0,
    ) -> tuple[Move | None, int, list[tuple[Move, int, int]]]:
        """Coup policier optimal, valeur associée et évaluations de tous les coups.

        Retourne `(meilleur_coup, valeur, [(coup, valeur, heuristique), ...])` trié
        du meilleur au pire. Les coups menant à une troisième répétition (nulle) sont
        déclassés au niveau « nulle » pour ne jamais gâcher une victoire forcée.
        """
        moves = police_legal_moves(self.graph, state, self.rules)
        if not moves:
            return None, _DRAW_VALUE, []

        child_k = min(ply + 1, self.cooldown)
        entries: list[tuple[tuple[int, int, int], Move, int, int]] = []
        for move in moves:
            child = apply_move(self.graph, state, move, self.rules, ply)
            value = self.value_sid(self.sid_of(child), child_k)
            heuristic = evaluate(self.graph, child, ply + 1, self.rules)
            repeat = 0
            if history_counts:
                repeat = history_counts.get(child.position_key(), 0)
                if (
                    repeat
                    and repetition_limit > 0
                    and repeat + 1 >= repetition_limit
                    and value != 0
                ):
                    if value < _DRAW_VALUE:
                        value = _DRAW_VALUE
            entries.append(((value, repeat, -heuristic), move, value, heuristic))

        entries.sort(key=lambda item: item[0])
        best_move = entries[0][1]
        best_value = entries[0][2]
        return (
            best_move,
            best_value,
            [(move, value, heuristic) for _, move, value, heuristic in entries],
        )

    def map_score(self, value: int, heuristic: int) -> int:
        if value < _DRAW_VALUE:
            return POLICE_WIN_SCORE - value
        if value > _DRAW_VALUE:
            return THIEF_WIN_SCORE + (_LOSE_BASE - value)
        return max(
            THIEF_WIN_SCORE + 1000,
            min(POLICE_WIN_SCORE - 1000, heuristic),
        )


# ---------------------------------------------------------------------- cache


_SOLVERS: dict[tuple, _SolvedGame] = {}
_SOLVER_LOCK = threading.Lock()


def _cache_directory() -> Path:
    return Path(tempfile.gettempdir()) / "police_voleur_solver"


def _cache_file(key: tuple) -> Path:
    digest = hashlib.sha1(repr(key).encode("utf-8")).hexdigest()[:20]
    return _cache_directory() / f"solver_{digest}.pkl"


def _load_cache(key: tuple):
    path = _cache_file(key)
    if not path.exists():
        return None
    try:
        with path.open("rb") as handle:
            payload = pickle.load(handle)
    except (OSError, pickle.PickleError, EOFError, ValueError):
        return None
    if not isinstance(payload, tuple) or len(payload) != 6:
        return None
    return payload


def _store_cache(key: tuple, payload) -> None:
    path = _cache_file(key)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".tmp")
        with temporary.open("wb") as handle:
            pickle.dump(payload, handle, protocol=pickle.HIGHEST_PROTOCOL)
        temporary.replace(path)
    except OSError:
        return


def solved_game(graph: Graph, rules: RuleSet = DEFAULT_RULES) -> _SolvedGame:
    """Retourne (et mémorise) le jeu résolu pour ce graphe et ces règles."""
    key = (
        tuple(sorted((min(e.u, e.v), max(e.u, e.v)) for e in graph.edges)),
        rules.return_cooldown,
        rules.center_contestable,
    )
    with _SOLVER_LOCK:
        solver = _SOLVERS.get(key)
        if solver is None:
            solver = _SolvedGame(graph, rules)
            _SOLVERS[key] = solver
        return solver


class PoliceSolverEngine:
    """Moteur de recherche exact de la POLICE ; interface compatible `SearchEngine`."""

    def __init__(self, graph: Graph) -> None:
        self.graph = graph
        self._history: tuple[GameState, ...] = ()
        self._repetition_limit = 0

    def set_context(
        self,
        history: tuple[GameState, ...] = (),
        repetition_limit: int = 0,
    ) -> None:
        """Contexte de partie (pour éviter les nulles par répétition)."""
        self._history = tuple(history)
        self._repetition_limit = int(repetition_limit)

    def search(
        self,
        state: GameState,
        config=None,
        ply: int = 0,
    ) -> SearchResult:
        started = time.perf_counter()
        rules = config.rules if config is not None else DEFAULT_RULES
        if state.turn is not Team.POLICE:
            raise ValueError("le solveur POLICE ne traite que les tours de la police")

        solver = solved_game(self.graph, rules)
        history_counts: dict[tuple, int] | None = None
        if self._history and self._repetition_limit > 0:
            history_counts = {}
            for previous in self._history:
                key = previous.position_key()
                history_counts[key] = history_counts.get(key, 0) + 1

        hits_before = solver.memo_hits
        move, value, entries = solver.best_move(
            state, ply, history_counts, self._repetition_limit
        )
        elapsed = time.perf_counter() - started

        if move is None:
            return SearchResult(
                move=None,
                score=evaluate(self.graph, state, ply, rules),
                depth=0,
                completed=True,
                nodes=solver.node_count,
                cutoffs=0,
                tt_hits=solver.memo_hits - hits_before,
                elapsed=elapsed,
            )

        root_scores = tuple(
            MoveEvaluation(entry_move, solver.map_score(entry_value, heuristic))
            for entry_move, entry_value, heuristic in entries
        )
        chosen_heuristic = next(
            heuristic for entry_move, _, heuristic in entries if entry_move == move
        )
        return SearchResult(
            move=move,
            score=solver.map_score(value, chosen_heuristic),
            depth=solver.distance(value),
            completed=True,
            nodes=solver.node_count,
            cutoffs=0,
            tt_hits=solver.memo_hits - hits_before,
            elapsed=elapsed,
            root_scores=root_scores,
            tree=None,
        )
