from __future__ import annotations

from dataclasses import dataclass
from math import inf
from time import perf_counter_ns
from typing import Optional

from crownline_ai import _actions, _evaluate
from crownline_game import Line
from crownline_rules import Participant
from crownline_search_engines import _structural_tt_key
from crownline_set import CrownlineSet
from crownline_time_engines import ClockNs, SearchDeadlineExceeded, _check_deadline


@dataclass(frozen=True)
class TTIterationSearchRecord:
    depth: int
    completed: bool
    elapsed_ms: float
    expanded_nodes: int
    cache_hits: int
    exact_entries: int
    cutoff_nodes: int
    notation: Optional[str] = None
    meld_line: Optional[Line] = None


@dataclass(frozen=True)
class TTIterativeDeepeningStats:
    budget_ms: float
    max_depth: int
    completed_depth: int
    attempted_depth: int
    timed_out: bool
    elapsed_ms: float
    deadline_overrun_ms: float
    total_expanded_nodes: int
    total_cache_hits: int
    total_exact_entries: int
    total_cutoff_nodes: int
    final_cache_size: int
    iterations: tuple[TTIterationSearchRecord, ...]


@dataclass
class _TTCounter:
    expanded_nodes: int = 0
    cache_hits: int = 0
    exact_entries: int = 0
    cutoff_nodes: int = 0


def _search_structural_tt_with_deadline(
    state: CrownlineSet,
    participant: Participant,
    depth: int,
    alpha: float,
    beta: float,
    *,
    deadline_ns: int,
    clock_ns: ClockNs,
    cache: dict[object, float],
    counter: _TTCounter,
) -> float:
    """Baseline A search plus the validated structural exact TT and a deadline.

    Cache entries are exact only. As in the fixed-depth structural-TT engine,
    alpha-beta cutoff nodes are never stored as exact values. The cache persists
    across iterative-deepening depths because its key includes remaining depth;
    reusing an entry from an earlier completed iteration therefore cannot change
    the mathematical value represented by that key.
    """

    _check_deadline(deadline_ns, clock_ns)
    key = _structural_tt_key(state, participant, depth)
    _check_deadline(deadline_ns, clock_ns)
    if key in cache:
        counter.cache_hits += 1
        return cache[key]

    counter.expanded_nodes += 1
    game = state.current_game
    if depth <= 0 or game.game_over:
        value = _evaluate(state, participant)
        _check_deadline(deadline_ns, clock_ns)
        cache[key] = value
        counter.exact_entries += 1
        return value

    actions = _actions(state)
    _check_deadline(deadline_ns, clock_ns)
    if not actions:
        value = _evaluate(state, participant)
        _check_deadline(deadline_ns, clock_ns)
        cache[key] = value
        counter.exact_entries += 1
        return value

    maximizing = state.participant_for_color(game.turn) == participant
    cutoff = False

    if maximizing:
        value = -inf
        for move, meld_line in actions:
            _check_deadline(deadline_ns, clock_ns)
            child = state.apply_move(move, meld_line=meld_line)
            value = max(
                value,
                _search_structural_tt_with_deadline(
                    child,
                    participant,
                    depth - 1,
                    alpha,
                    beta,
                    deadline_ns=deadline_ns,
                    clock_ns=clock_ns,
                    cache=cache,
                    counter=counter,
                ),
            )
            alpha = max(alpha, value)
            if alpha >= beta:
                cutoff = True
                counter.cutoff_nodes += 1
                break
    else:
        value = inf
        for move, meld_line in actions:
            _check_deadline(deadline_ns, clock_ns)
            child = state.apply_move(move, meld_line=meld_line)
            value = min(
                value,
                _search_structural_tt_with_deadline(
                    child,
                    participant,
                    depth - 1,
                    alpha,
                    beta,
                    deadline_ns=deadline_ns,
                    clock_ns=clock_ns,
                    cache=cache,
                    counter=counter,
                ),
            )
            beta = min(beta, value)
            if alpha >= beta:
                cutoff = True
                counter.cutoff_nodes += 1
                break

    _check_deadline(deadline_ns, clock_ns)
    if not cutoff:
        cache[key] = value
        counter.exact_entries += 1
    return value


def _choose_completed_depth_structural_tt(
    state: CrownlineSet,
    participant: Participant,
    *,
    depth: int,
    root_actions,
    deadline_ns: int,
    clock_ns: ClockNs,
    cache: dict[object, float],
    counter: _TTCounter,
) -> tuple[str, Optional[Line]]:
    _check_deadline(deadline_ns, clock_ns)
    ranked = []
    for move, meld_line in root_actions:
        _check_deadline(deadline_ns, clock_ns)
        child = state.apply_move(move, meld_line=meld_line)
        value = _search_structural_tt_with_deadline(
            child,
            participant,
            max(0, depth - 1),
            -inf,
            inf,
            deadline_ns=deadline_ns,
            clock_ns=clock_ns,
            cache=cache,
            counter=counter,
        )
        line_key = "-".join(meld_line) if meld_line else ""
        ranked.append((value, move.notation(), line_key, meld_line))

    _check_deadline(deadline_ns, clock_ns)
    best_value = max(item[0] for item in ranked)
    best = min(
        (item for item in ranked if item[0] == best_value),
        key=lambda item: (item[1], item[2]),
    )
    return best[1], best[3]


def choose_computer_action_iterative_structural_tt(
    state: CrownlineSet,
    participant: Participant = "B",
    *,
    budget_ms: float = 150.0,
    max_depth: int = 4,
    clock_ns: ClockNs = perf_counter_ns,
) -> tuple[str, Optional[Line], TTIterativeDeepeningStats]:
    """Iterative deepening with a persistent CLSN-equivalent structural exact TT.

    The authoritative action is always from the deepest fully completed depth.
    A partial iteration is discarded. The exact cache survives between completed
    iterative depths, but every key includes remaining depth and participant
    perspective, so reuse remains semantics-preserving.
    """

    if budget_ms <= 0:
        raise ValueError("budget_ms must be positive")
    if max_depth < 1 or max_depth > 4:
        raise ValueError("max_depth must be between 1 and 4")
    if state.set_over:
        raise ValueError("Set is already over")
    game = state.current_game
    if game.game_over:
        raise ValueError("Current game is already over")
    if state.participant_for_color(game.turn) != participant:
        raise ValueError(f"It is not Player {participant}'s turn")

    started_ns = clock_ns()
    deadline_ns = started_ns + max(1, int(budget_ms * 1_000_000.0))
    root_actions = _actions(state)
    if not root_actions:
        raise ValueError("No legal computer move is available")

    fallback = min(
        (
            move.notation(),
            "-".join(meld_line) if meld_line else "",
            meld_line,
        )
        for move, meld_line in root_actions
    )
    best_notation, _, best_meld_line = fallback

    cache: dict[object, float] = {}
    iterations: list[TTIterationSearchRecord] = []
    completed_depth = 0
    attempted_depth = 0
    timed_out = False

    for depth in range(1, max_depth + 1):
        attempted_depth = depth
        iteration_started_ns = clock_ns()
        counter = _TTCounter()
        try:
            notation, meld_line = _choose_completed_depth_structural_tt(
                state,
                participant,
                depth=depth,
                root_actions=root_actions,
                deadline_ns=deadline_ns,
                clock_ns=clock_ns,
                cache=cache,
                counter=counter,
            )
        except SearchDeadlineExceeded:
            timed_out = True
            iterations.append(
                TTIterationSearchRecord(
                    depth=depth,
                    completed=False,
                    elapsed_ms=max(
                        0.0,
                        (clock_ns() - iteration_started_ns) / 1_000_000.0,
                    ),
                    expanded_nodes=counter.expanded_nodes,
                    cache_hits=counter.cache_hits,
                    exact_entries=counter.exact_entries,
                    cutoff_nodes=counter.cutoff_nodes,
                )
            )
            break

        iterations.append(
            TTIterationSearchRecord(
                depth=depth,
                completed=True,
                elapsed_ms=max(
                    0.0,
                    (clock_ns() - iteration_started_ns) / 1_000_000.0,
                ),
                expanded_nodes=counter.expanded_nodes,
                cache_hits=counter.cache_hits,
                exact_entries=counter.exact_entries,
                cutoff_nodes=counter.cutoff_nodes,
                notation=notation,
                meld_line=meld_line,
            )
        )
        completed_depth = depth
        best_notation = notation
        best_meld_line = meld_line

    finished_ns = clock_ns()
    elapsed_ms = max(0.0, (finished_ns - started_ns) / 1_000_000.0)
    stats = TTIterativeDeepeningStats(
        budget_ms=float(budget_ms),
        max_depth=max_depth,
        completed_depth=completed_depth,
        attempted_depth=attempted_depth,
        timed_out=timed_out,
        elapsed_ms=elapsed_ms,
        deadline_overrun_ms=max(0.0, elapsed_ms - float(budget_ms)),
        total_expanded_nodes=sum(item.expanded_nodes for item in iterations),
        total_cache_hits=sum(item.cache_hits for item in iterations),
        total_exact_entries=sum(item.exact_entries for item in iterations),
        total_cutoff_nodes=sum(item.cutoff_nodes for item in iterations),
        final_cache_size=len(cache),
        iterations=tuple(iterations),
    )
    return best_notation, best_meld_line, stats
