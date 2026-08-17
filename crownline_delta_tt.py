from __future__ import annotations

from dataclasses import dataclass
from math import inf
from time import perf_counter_ns
from typing import Optional

from crownline_ai import _actions, _evaluate
from crownline_benchmark import EngineDecision
from crownline_delta_ordering import _delta_estimate_for_child
from crownline_game import Line
from crownline_rules import Participant, Player
from crownline_search_engines import _structural_game_identity
from crownline_set import CrownlineSet


@dataclass
class DeltaOrderedTTSearchStats:
    expanded_nodes: int = 0
    cache_hits: int = 0
    exact_entries: int = 0
    cutoff_nodes: int = 0
    ordering_estimates: int = 0
    parent_score_scans: int = 0

    @property
    def probes(self) -> int:
        return self.expanded_nodes + self.cache_hits

    @property
    def hit_rate(self) -> float:
        return self.cache_hits / self.probes if self.probes else 0.0


def _key(state: CrownlineSet, participant: Participant, depth: int) -> tuple:
    return (
        _structural_game_identity(state),
        state.white_participant,
        participant,
        depth,
    )


def _ordered_children(
    state: CrownlineSet,
    participant: Participant,
    *,
    maximizing: bool,
    stats: DeltaOrderedTTSearchStats,
) -> tuple[CrownlineSet, ...]:
    game = state.current_game
    parent_score_by_color: dict[Player, int] = {
        "W": game.score("W").total,
        "B": game.score("B").total,
    }
    stats.parent_score_scans += 1

    ranked = []
    for move, meld_line in _actions(state):
        child = state.apply_move(move, meld_line=meld_line)
        estimate = _delta_estimate_for_child(
            state,
            child,
            move,
            participant,
            parent_score_by_color=parent_score_by_color,
        )
        stats.ordering_estimates += 1
        line_key = "-".join(meld_line) if meld_line else ""
        ranked.append((estimate, move.notation(), line_key, child))

    if maximizing:
        ranked.sort(key=lambda item: (-item[0], item[1], item[2]))
    else:
        ranked.sort(key=lambda item: (item[0], item[1], item[2]))
    return tuple(item[3] for item in ranked)


def _search(
    state: CrownlineSet,
    participant: Participant,
    depth: int,
    alpha: float,
    beta: float,
    cache: dict[tuple, float],
    stats: DeltaOrderedTTSearchStats,
) -> float:
    key = _key(state, participant, depth)
    if key in cache:
        stats.cache_hits += 1
        return cache[key]

    stats.expanded_nodes += 1
    game = state.current_game
    if depth <= 0 or game.game_over:
        value = _evaluate(state, participant)
        cache[key] = value
        stats.exact_entries += 1
        return value

    actions = _actions(state)
    if not actions:
        value = _evaluate(state, participant)
        cache[key] = value
        stats.exact_entries += 1
        return value

    maximizing = state.participant_for_color(game.turn) == participant
    children = _ordered_children(
        state,
        participant,
        maximizing=maximizing,
        stats=stats,
    )
    cutoff = False

    if maximizing:
        value = -inf
        for child in children:
            value = max(
                value,
                _search(
                    child,
                    participant,
                    depth - 1,
                    alpha,
                    beta,
                    cache,
                    stats,
                ),
            )
            alpha = max(alpha, value)
            if alpha >= beta:
                cutoff = True
                stats.cutoff_nodes += 1
                break
    else:
        value = inf
        for child in children:
            value = min(
                value,
                _search(
                    child,
                    participant,
                    depth - 1,
                    alpha,
                    beta,
                    cache,
                    stats,
                ),
            )
            beta = min(beta, value)
            if alpha >= beta:
                cutoff = True
                stats.cutoff_nodes += 1
                break

    if not cutoff:
        cache[key] = value
        stats.exact_entries += 1
    return value


def choose_computer_action_delta_ordered_tt(
    state: CrownlineSet,
    participant: Participant = "B",
    *,
    depth: int = 2,
) -> tuple[str, Optional[Line], DeltaOrderedTTSearchStats]:
    if depth < 1 or depth > 4:
        raise ValueError("Delta-ordered TT depth must be between 1 and 4")
    if state.set_over:
        raise ValueError("Set is already over")
    game = state.current_game
    if game.game_over:
        raise ValueError("Current game is already over")
    if state.participant_for_color(game.turn) != participant:
        raise ValueError(f"It is not Player {participant}'s turn")

    actions = _actions(state)
    if not actions:
        raise ValueError("No legal computer move is available")

    cache: dict[tuple, float] = {}
    stats = DeltaOrderedTTSearchStats()
    ranked = []
    for move, meld_line in actions:
        child = state.apply_move(move, meld_line=meld_line)
        value = _search(
            child,
            participant,
            max(0, depth - 1),
            -inf,
            inf,
            cache,
            stats,
        )
        line_key = "-".join(meld_line) if meld_line else ""
        ranked.append((value, move.notation(), line_key, meld_line))

    best_value = max(item[0] for item in ranked)
    best = min(
        (item for item in ranked if item[0] == best_value),
        key=lambda item: (item[1], item[2]),
    )
    return best[1], best[3], stats


@dataclass
class DeltaScoreOrderedStructuralTTBaselineEngine:
    """Baseline A policy with delta ordering + structural exact TT."""

    name: str
    depth: int = 2
    total_expanded_nodes: int = 0
    total_cache_hits: int = 0
    total_exact_entries: int = 0
    total_cutoff_nodes: int = 0
    total_ordering_estimates: int = 0
    total_parent_score_scans: int = 0

    def __post_init__(self) -> None:
        if self.depth < 1 or self.depth > 4:
            raise ValueError(
                "DeltaScoreOrderedStructuralTTBaselineEngine depth must be between 1 and 4"
            )

    def choose(self, state: CrownlineSet, participant: Participant) -> EngineDecision:
        root_actions = len(_actions(state))
        started = perf_counter_ns()
        notation, meld_line, stats = choose_computer_action_delta_ordered_tt(
            state,
            participant=participant,
            depth=self.depth,
        )
        elapsed_ms = (perf_counter_ns() - started) / 1_000_000.0

        self.total_expanded_nodes += stats.expanded_nodes
        self.total_cache_hits += stats.cache_hits
        self.total_exact_entries += stats.exact_entries
        self.total_cutoff_nodes += stats.cutoff_nodes
        self.total_ordering_estimates += stats.ordering_estimates
        self.total_parent_score_scans += stats.parent_score_scans

        return EngineDecision(
            notation=notation,
            meld_line=meld_line,
            elapsed_ms=elapsed_ms,
            search_nodes=stats.expanded_nodes,
            root_actions=root_actions,
        )
