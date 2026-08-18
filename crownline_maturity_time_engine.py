from __future__ import annotations

from dataclasses import dataclass
from math import inf
from time import perf_counter_ns
from typing import Optional

from crownline_ai import _actions
from crownline_benchmark import EngineDecision
from crownline_game import Line
from crownline_promotion_maturity_experiment import evaluate_with_promotion_maturity
from crownline_rules import Participant
from crownline_search_engines import _structural_tt_key
from crownline_set import CrownlineSet
from crownline_time_engines import ClockNs, SearchDeadlineExceeded, _check_deadline
from crownline_tt_time_engine import (
    TTIterationSearchRecord,
    TTIterativeDeepeningStats,
    _TTCounter,
)


def _search_maturity_structural_tt_with_deadline(
    state: CrownlineSet,
    participant: Participant,
    depth: int,
    alpha: float,
    beta: float,
    *,
    maturity_weight: float,
    deadline_ns: int,
    clock_ns: ClockNs,
    cache: dict[object, float],
    counter: _TTCounter,
) -> float:
    """Stage-2 exact structural-TT search with one evaluator substitution.

    The search semantics, move order, alpha-beta cutoffs, exact-entry discipline,
    structural key, and deadline behavior are unchanged. Only nonterminal leaf
    evaluation differs, via the independently measured promotion-maturity term.
    The cache is local to one decision and one fixed maturity weight.
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
        value = evaluate_with_promotion_maturity(
            state,
            participant,
            maturity_weight=maturity_weight,
        )
        _check_deadline(deadline_ns, clock_ns)
        cache[key] = value
        counter.exact_entries += 1
        return value

    actions = _actions(state)
    _check_deadline(deadline_ns, clock_ns)
    if not actions:
        value = evaluate_with_promotion_maturity(
            state,
            participant,
            maturity_weight=maturity_weight,
        )
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
                _search_maturity_structural_tt_with_deadline(
                    child,
                    participant,
                    depth - 1,
                    alpha,
                    beta,
                    maturity_weight=maturity_weight,
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
                _search_maturity_structural_tt_with_deadline(
                    child,
                    participant,
                    depth - 1,
                    alpha,
                    beta,
                    maturity_weight=maturity_weight,
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


def choose_computer_action_iterative_structural_tt_maturity(
    state: CrownlineSet,
    participant: Participant = "B",
    *,
    budget_ms: float = 150.0,
    max_depth: int = 4,
    maturity_weight: float = 10.0,
    clock_ns: ClockNs = perf_counter_ns,
) -> tuple[str, Optional[Line], TTIterativeDeepeningStats]:
    """Stage-2 iterative structural-TT search plus promotion maturity only."""

    if budget_ms <= 0:
        raise ValueError("budget_ms must be positive")
    if max_depth < 1 or max_depth > 4:
        raise ValueError("max_depth must be between 1 and 4")
    if maturity_weight < 0:
        raise ValueError("maturity_weight must be non-negative")
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
            _check_deadline(deadline_ns, clock_ns)
            ranked = []
            for move, meld_line in root_actions:
                _check_deadline(deadline_ns, clock_ns)
                child = state.apply_move(move, meld_line=meld_line)
                value = _search_maturity_structural_tt_with_deadline(
                    child,
                    participant,
                    max(0, depth - 1),
                    -inf,
                    inf,
                    maturity_weight=maturity_weight,
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
        except SearchDeadlineExceeded:
            timed_out = True
            iterations.append(
                TTIterationSearchRecord(
                    depth=depth,
                    completed=False,
                    elapsed_ms=max(0.0, (clock_ns() - iteration_started_ns) / 1_000_000.0),
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
                elapsed_ms=max(0.0, (clock_ns() - iteration_started_ns) / 1_000_000.0),
                expanded_nodes=counter.expanded_nodes,
                cache_hits=counter.cache_hits,
                exact_entries=counter.exact_entries,
                cutoff_nodes=counter.cutoff_nodes,
                notation=best[1],
                meld_line=best[3],
            )
        )
        completed_depth = depth
        best_notation = best[1]
        best_meld_line = best[3]

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


@dataclass
class PromotionMaturityStructuralTTTimeControl:
    """150 ms product-regime adapter for the isolated maturity evaluator."""

    name: str = "stage2-tt-plus-maturity-w10"
    budget_ms: float = 150.0
    max_depth: int = 4
    maturity_weight: float = 10.0
    clock_ns: ClockNs = perf_counter_ns
    completed_depth_total: int = 0
    decisions: int = 0
    timed_out_decisions: int = 0

    def __post_init__(self) -> None:
        if self.budget_ms <= 0:
            raise ValueError("budget_ms must be positive")
        if self.max_depth < 1 or self.max_depth > 4:
            raise ValueError("max_depth must be between 1 and 4")
        if self.maturity_weight < 0:
            raise ValueError("maturity_weight must be non-negative")

    @property
    def mean_completed_depth(self) -> float:
        return self.completed_depth_total / self.decisions if self.decisions else 0.0

    def choose(self, state: CrownlineSet, participant: Participant) -> EngineDecision:
        notation, meld_line, stats = choose_computer_action_iterative_structural_tt_maturity(
            state,
            participant=participant,
            budget_ms=self.budget_ms,
            max_depth=self.max_depth,
            maturity_weight=self.maturity_weight,
            clock_ns=self.clock_ns,
        )
        self.decisions += 1
        self.completed_depth_total += stats.completed_depth
        self.timed_out_decisions += int(stats.timed_out)
        return EngineDecision(
            notation=notation,
            meld_line=meld_line,
            elapsed_ms=stats.elapsed_ms,
            search_nodes=stats.total_expanded_nodes,
            root_actions=len(_actions(state)),
        )
