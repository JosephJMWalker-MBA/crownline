from __future__ import annotations

from dataclasses import dataclass, field
from math import inf
from time import perf_counter_ns
from typing import Optional

from crownline_ai import _actions
from crownline_benchmark import EngineDecision
from crownline_game import Line
from crownline_rules import Participant
from crownline_set import CrownlineSet
from crownline_state_notation import clsn_fingerprint
from crownline_time_engines import ClockNs, SearchDeadlineExceeded, _check_deadline
from crownline_tt_time_engine import (
    TTIterationSearchRecord,
    TTIterativeDeepeningStats,
    _TTCounter,
    _search_structural_tt_with_deadline,
    choose_computer_action_iterative_structural_tt,
)


@dataclass(frozen=True)
class ProductCandidateDecisionStats:
    """Search evidence plus the independently measured root history policy."""

    search: TTIterativeDeepeningStats
    repeat_penalty: float
    repeat_candidates_at_root: int
    selected_repeat_count: int
    selected_afterstate: str


@dataclass
class RepeatAwareStructuralTTOpponent:
    """First coherent Crownline opponent candidate supported by Stages 2 and 3.

    Search substrate (Stage 2):
      * iterative deepening under a soft wall-clock budget;
      * CLSN-equivalent structural exact transposition table;
      * deepest fully completed iteration only.

    Trajectory policy (Stage 3):
      * a 50-point default root penalty when an action recreates an exact CLSN
        afterstate this participant has already produced in the current game.

    The static evaluator, legal moves, alpha-beta semantics, and Crownline rules
    are unchanged. The quota-horizon experiment is deliberately excluded because
    it did not earn inclusion in direct composition evidence.
    """

    name: str = "stage2-tt-plus-repeat-p50"
    budget_ms: float = 150.0
    max_depth: int = 4
    repeat_penalty: float = 50.0
    clock_ns: ClockNs = perf_counter_ns
    _game_number: Optional[int] = field(default=None, init=False, repr=False)
    _last_seen_ply: Optional[int] = field(default=None, init=False, repr=False)
    _produced_afterstates: dict[str, int] = field(default_factory=dict, init=False, repr=False)
    repeat_candidates_seen: int = field(default=0, init=False)
    decisions_with_repeat_candidate: int = field(default=0, init=False)
    repeated_action_selected: int = field(default=0, init=False)
    completed_depth_total: int = field(default=0, init=False)
    decisions: int = field(default=0, init=False)
    timed_out_decisions: int = field(default=0, init=False)

    def __post_init__(self) -> None:
        if self.budget_ms <= 0:
            raise ValueError("budget_ms must be positive")
        if self.max_depth < 1 or self.max_depth > 4:
            raise ValueError("max_depth must be between 1 and 4")
        if self.repeat_penalty < 0:
            raise ValueError("repeat_penalty must be non-negative")

    @property
    def memory_size(self) -> int:
        return len(self._produced_afterstates)

    @property
    def mean_completed_depth(self) -> float:
        return self.completed_depth_total / self.decisions if self.decisions else 0.0

    def _maybe_reset_for_game(self, state: CrownlineSet) -> None:
        game = state.current_game
        if (
            self._game_number is None
            or game.variant.number != self._game_number
            or (
                self._last_seen_ply is not None
                and game.ply <= self._last_seen_ply
            )
        ):
            self._game_number = game.variant.number
            self._produced_afterstates.clear()
        self._last_seen_ply = game.ply

    def _choose(self, state: CrownlineSet, participant: Participant) -> tuple[str, Optional[Line], ProductCandidateDecisionStats]:
        if state.set_over:
            raise ValueError("Set is already over")
        game = state.current_game
        if game.game_over:
            raise ValueError("Current game is already over")
        if state.participant_for_color(game.turn) != participant:
            raise ValueError(f"It is not Player {participant}'s turn")

        self._maybe_reset_for_game(state)
        started_ns = self.clock_ns()
        deadline_ns = started_ns + max(1, int(self.budget_ms * 1_000_000.0))
        root_actions = _actions(state)
        if not root_actions:
            raise ValueError("No legal computer move is available")

        root_meta = []
        for move, meld_line in root_actions:
            child = state.apply_move(move, meld_line=meld_line)
            fingerprint = clsn_fingerprint(child.current_game)
            repeat_count = self._produced_afterstates.get(fingerprint, 0)
            line_key = "-".join(meld_line) if meld_line else ""
            root_meta.append((move, meld_line, line_key, fingerprint, repeat_count))

        fallback = min(root_meta, key=lambda item: (item[0].notation(), item[2]))
        best_notation = fallback[0].notation()
        best_meld_line = fallback[1]
        best_fingerprint = fallback[3]
        best_repeat_count = fallback[4]

        cache: dict[object, float] = {}
        iterations: list[TTIterationSearchRecord] = []
        completed_depth = 0
        attempted_depth = 0
        timed_out = False

        for depth in range(1, self.max_depth + 1):
            attempted_depth = depth
            iteration_started_ns = self.clock_ns()
            counter = _TTCounter()
            try:
                _check_deadline(deadline_ns, self.clock_ns)
                ranked = []
                for move, meld_line, line_key, fingerprint, repeat_count in root_meta:
                    _check_deadline(deadline_ns, self.clock_ns)
                    child = state.apply_move(move, meld_line=meld_line)
                    value = _search_structural_tt_with_deadline(
                        child,
                        participant,
                        max(0, depth - 1),
                        -inf,
                        inf,
                        deadline_ns=deadline_ns,
                        clock_ns=self.clock_ns,
                        cache=cache,
                        counter=counter,
                    )
                    adjusted = value - self.repeat_penalty * repeat_count
                    ranked.append(
                        (
                            adjusted,
                            value,
                            move.notation(),
                            line_key,
                            meld_line,
                            fingerprint,
                            repeat_count,
                        )
                    )
                _check_deadline(deadline_ns, self.clock_ns)
                best_adjusted = max(item[0] for item in ranked)
                best = min(
                    (item for item in ranked if item[0] == best_adjusted),
                    key=lambda item: (item[2], item[3]),
                )
            except SearchDeadlineExceeded:
                timed_out = True
                iterations.append(
                    TTIterationSearchRecord(
                        depth=depth,
                        completed=False,
                        elapsed_ms=max(
                            0.0,
                            (self.clock_ns() - iteration_started_ns) / 1_000_000.0,
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
                        (self.clock_ns() - iteration_started_ns) / 1_000_000.0,
                    ),
                    expanded_nodes=counter.expanded_nodes,
                    cache_hits=counter.cache_hits,
                    exact_entries=counter.exact_entries,
                    cutoff_nodes=counter.cutoff_nodes,
                    notation=best[2],
                    meld_line=best[4],
                )
            )
            completed_depth = depth
            best_notation = best[2]
            best_meld_line = best[4]
            best_fingerprint = best[5]
            best_repeat_count = best[6]

        finished_ns = self.clock_ns()
        elapsed_ms = max(0.0, (finished_ns - started_ns) / 1_000_000.0)
        search_stats = TTIterativeDeepeningStats(
            budget_ms=float(self.budget_ms),
            max_depth=self.max_depth,
            completed_depth=completed_depth,
            attempted_depth=attempted_depth,
            timed_out=timed_out,
            elapsed_ms=elapsed_ms,
            deadline_overrun_ms=max(0.0, elapsed_ms - float(self.budget_ms)),
            total_expanded_nodes=sum(item.expanded_nodes for item in iterations),
            total_cache_hits=sum(item.cache_hits for item in iterations),
            total_exact_entries=sum(item.exact_entries for item in iterations),
            total_cutoff_nodes=sum(item.cutoff_nodes for item in iterations),
            final_cache_size=len(cache),
            iterations=tuple(iterations),
        )
        stats = ProductCandidateDecisionStats(
            search=search_stats,
            repeat_penalty=self.repeat_penalty,
            repeat_candidates_at_root=sum(item[4] > 0 for item in root_meta),
            selected_repeat_count=best_repeat_count,
            selected_afterstate=best_fingerprint,
        )
        return best_notation, best_meld_line, stats

    def choose_with_stats(self, state: CrownlineSet, participant: Participant) -> tuple[str, Optional[Line], ProductCandidateDecisionStats]:
        notation, meld_line, stats = self._choose(state, participant)
        self.repeat_candidates_seen += stats.repeat_candidates_at_root
        self.decisions_with_repeat_candidate += int(stats.repeat_candidates_at_root > 0)
        self.repeated_action_selected += int(stats.selected_repeat_count > 0)
        self._produced_afterstates[stats.selected_afterstate] = self._produced_afterstates.get(stats.selected_afterstate, 0) + 1
        self.decisions += 1
        self.completed_depth_total += stats.search.completed_depth
        self.timed_out_decisions += int(stats.search.timed_out)
        return notation, meld_line, stats

    def choose(self, state: CrownlineSet, participant: Participant) -> EngineDecision:
        notation, meld_line, stats = self.choose_with_stats(state, participant)
        return EngineDecision(
            notation=notation,
            meld_line=meld_line,
            elapsed_ms=stats.search.elapsed_ms,
            search_nodes=stats.search.total_expanded_nodes,
            root_actions=len(_actions(state)),
        )


@dataclass
class StructuralTTTimeControl:
    """Benchmark adapter for the Stage-2 search substrate without history policy."""

    name: str = "stage2-structural-tt-control"
    budget_ms: float = 150.0
    max_depth: int = 4
    clock_ns: ClockNs = perf_counter_ns
    completed_depth_total: int = 0
    decisions: int = 0
    timed_out_decisions: int = 0

    @property
    def mean_completed_depth(self) -> float:
        return self.completed_depth_total / self.decisions if self.decisions else 0.0

    def choose(self, state: CrownlineSet, participant: Participant) -> EngineDecision:
        notation, meld_line, stats = choose_computer_action_iterative_structural_tt(
            state,
            participant=participant,
            budget_ms=self.budget_ms,
            max_depth=self.max_depth,
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
