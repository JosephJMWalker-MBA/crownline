from __future__ import annotations

from dataclasses import dataclass
from math import inf
from time import perf_counter_ns
from typing import Callable, Optional

from crownline_ai import _actions, _evaluate
from crownline_game import Line
from crownline_rules import Participant
from crownline_set import CrownlineSet


ClockNs = Callable[[], int]


class SearchDeadlineExceeded(RuntimeError):
    """Internal control flow used to discard an incomplete depth iteration."""


@dataclass(frozen=True)
class IterationSearchRecord:
    depth: int
    completed: bool
    elapsed_ms: float
    search_nodes: int
    notation: Optional[str] = None
    meld_line: Optional[Line] = None


@dataclass(frozen=True)
class IterativeDeepeningStats:
    budget_ms: float
    max_depth: int
    completed_depth: int
    attempted_depth: int
    timed_out: bool
    elapsed_ms: float
    deadline_overrun_ms: float
    total_search_nodes: int
    iterations: tuple[IterationSearchRecord, ...]


@dataclass
class _NodeCounter:
    nodes: int = 0


def _check_deadline(deadline_ns: int, clock_ns: ClockNs) -> None:
    if clock_ns() >= deadline_ns:
        raise SearchDeadlineExceeded


def _search_with_deadline(
    state: CrownlineSet,
    participant: Participant,
    depth: int,
    alpha: float,
    beta: float,
    *,
    deadline_ns: int,
    clock_ns: ClockNs,
    counter: _NodeCounter,
) -> float:
    """Baseline A alpha-beta search with deadline checks only.

    Action order, evaluator, alpha-beta semantics, and leaf values are identical
    to `crownline_ai._search`. Deadline expiration aborts the entire current
    iterative-deepening depth; a partial result is never promoted.
    """

    _check_deadline(deadline_ns, clock_ns)
    counter.nodes += 1

    game = state.current_game
    if depth <= 0 or game.game_over:
        value = _evaluate(state, participant)
        _check_deadline(deadline_ns, clock_ns)
        return value

    actions = _actions(state)
    _check_deadline(deadline_ns, clock_ns)
    if not actions:
        value = _evaluate(state, participant)
        _check_deadline(deadline_ns, clock_ns)
        return value

    maximizing = state.participant_for_color(game.turn) == participant

    if maximizing:
        value = -inf
        for move, meld_line in actions:
            _check_deadline(deadline_ns, clock_ns)
            child = state.apply_move(move, meld_line=meld_line)
            value = max(
                value,
                _search_with_deadline(
                    child,
                    participant,
                    depth - 1,
                    alpha,
                    beta,
                    deadline_ns=deadline_ns,
                    clock_ns=clock_ns,
                    counter=counter,
                ),
            )
            alpha = max(alpha, value)
            if alpha >= beta:
                break
        _check_deadline(deadline_ns, clock_ns)
        return value

    value = inf
    for move, meld_line in actions:
        _check_deadline(deadline_ns, clock_ns)
        child = state.apply_move(move, meld_line=meld_line)
        value = min(
            value,
            _search_with_deadline(
                child,
                participant,
                depth - 1,
                alpha,
                beta,
                deadline_ns=deadline_ns,
                clock_ns=clock_ns,
                counter=counter,
            ),
        )
        beta = min(beta, value)
        if alpha >= beta:
            break
    _check_deadline(deadline_ns, clock_ns)
    return value


def _choose_completed_depth(
    state: CrownlineSet,
    participant: Participant,
    *,
    depth: int,
    root_actions,
    deadline_ns: int,
    clock_ns: ClockNs,
    counter: _NodeCounter,
) -> tuple[str, Optional[Line]]:
    """Run one fixed depth, preserving Baseline A's root tie-breaking exactly."""

    _check_deadline(deadline_ns, clock_ns)
    ranked = []
    for move, meld_line in root_actions:
        _check_deadline(deadline_ns, clock_ns)
        child = state.apply_move(move, meld_line=meld_line)
        value = _search_with_deadline(
            child,
            participant,
            max(0, depth - 1),
            -inf,
            inf,
            deadline_ns=deadline_ns,
            clock_ns=clock_ns,
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


def choose_computer_action_iterative_baseline(
    state: CrownlineSet,
    participant: Participant = "B",
    *,
    budget_ms: float = 150.0,
    max_depth: int = 4,
    clock_ns: ClockNs = perf_counter_ns,
) -> tuple[str, Optional[Line], IterativeDeepeningStats]:
    """Choose Baseline A's deepest fully completed search within a soft deadline.

    Search proceeds depth 1 -> `max_depth`. If the deadline expires during an
    iteration, that partial iteration is discarded and the action from the last
    fully completed depth is returned. If depth 1 cannot complete, the engine
    falls back to Baseline A's deterministic lexicographic root-action order and
    reports `completed_depth == 0`.

    The budget includes initial root-action enumeration and all completed and
    abandoned iterative-deepening work. `deadline_overrun_ms` exposes the small
    scheduling/check granularity rather than pretending a Python deadline is a
    hard real-time guarantee.
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

    iterations: list[IterationSearchRecord] = []
    completed_depth = 0
    attempted_depth = 0
    timed_out = False

    for depth in range(1, max_depth + 1):
        attempted_depth = depth
        iteration_started_ns = clock_ns()
        counter = _NodeCounter()
        try:
            notation, meld_line = _choose_completed_depth(
                state,
                participant,
                depth=depth,
                root_actions=root_actions,
                deadline_ns=deadline_ns,
                clock_ns=clock_ns,
                counter=counter,
            )
        except SearchDeadlineExceeded:
            timed_out = True
            iteration_elapsed_ms = max(
                0.0,
                (clock_ns() - iteration_started_ns) / 1_000_000.0,
            )
            iterations.append(
                IterationSearchRecord(
                    depth=depth,
                    completed=False,
                    elapsed_ms=iteration_elapsed_ms,
                    search_nodes=counter.nodes,
                )
            )
            break

        iteration_elapsed_ms = max(
            0.0,
            (clock_ns() - iteration_started_ns) / 1_000_000.0,
        )
        iterations.append(
            IterationSearchRecord(
                depth=depth,
                completed=True,
                elapsed_ms=iteration_elapsed_ms,
                search_nodes=counter.nodes,
                notation=notation,
                meld_line=meld_line,
            )
        )
        completed_depth = depth
        best_notation = notation
        best_meld_line = meld_line

    finished_ns = clock_ns()
    elapsed_ms = max(0.0, (finished_ns - started_ns) / 1_000_000.0)
    stats = IterativeDeepeningStats(
        budget_ms=float(budget_ms),
        max_depth=max_depth,
        completed_depth=completed_depth,
        attempted_depth=attempted_depth,
        timed_out=timed_out,
        elapsed_ms=elapsed_ms,
        deadline_overrun_ms=max(0.0, elapsed_ms - float(budget_ms)),
        total_search_nodes=sum(item.search_nodes for item in iterations),
        iterations=tuple(iterations),
    )
    return best_notation, best_meld_line, stats
