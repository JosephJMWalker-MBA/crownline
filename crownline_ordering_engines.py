from __future__ import annotations

from dataclasses import dataclass
from math import inf
from time import perf_counter_ns
from typing import Optional

from crownline_ai import _actions, _evaluate
from crownline_benchmark import EngineDecision
from crownline_game import Line
from crownline_rules import Participant, opponent
from crownline_set import CrownlineSet


@dataclass
class ScoreOrderedSearchStats:
    """Per-decision measurements for cheap score-only move ordering."""

    expanded_nodes: int = 0
    cutoff_nodes: int = 0
    ordering_estimates: int = 0


def _score_only_estimate(state: CrownlineSet, participant: Participant) -> float:
    """Approximate Baseline A's dominant static terms without mobility search.

    Baseline A's evaluator is score margin * 100, plus meld-count margin * 8,
    plus a legal-move-count mobility term. The mobility term is the expensive
    part to recompute merely for ordering. This estimator deliberately omits it
    while preserving the score/meld terms and terminal scaling.

    The estimate affects child visitation order only. Leaf values still use the
    unchanged authoritative `_evaluate`, so minimax policy must remain identical.
    """

    game = state.current_game
    my_color = state.color_for_participant(participant)
    their_color = opponent(my_color)
    score_margin = game.score(my_color).total - game.score(their_color).total
    if game.game_over:
        return score_margin * 1000.0

    my_melds = len(game.melds(my_color))
    their_melds = len(game.melds(their_color))
    return score_margin * 100.0 + (my_melds - their_melds) * 8


def _ordered_children(
    state: CrownlineSet,
    participant: Participant,
    *,
    maximizing: bool,
    stats: ScoreOrderedSearchStats,
) -> tuple[CrownlineSet, ...]:
    ranked = []
    for move, meld_line in _actions(state):
        child = state.apply_move(move, meld_line=meld_line)
        estimate = _score_only_estimate(child, participant)
        stats.ordering_estimates += 1
        line_key = "-".join(meld_line) if meld_line else ""
        ranked.append((estimate, move.notation(), line_key, child))

    if maximizing:
        ranked.sort(key=lambda item: (-item[0], item[1], item[2]))
    else:
        ranked.sort(key=lambda item: (item[0], item[1], item[2]))
    return tuple(item[3] for item in ranked)


def _search_score_ordered(
    state: CrownlineSet,
    participant: Participant,
    depth: int,
    alpha: float,
    beta: float,
    stats: ScoreOrderedSearchStats,
) -> float:
    stats.expanded_nodes += 1
    game = state.current_game
    if depth <= 0 or game.game_over:
        return _evaluate(state, participant)

    actions = _actions(state)
    if not actions:
        return _evaluate(state, participant)

    maximizing = state.participant_for_color(game.turn) == participant
    children = _ordered_children(
        state,
        participant,
        maximizing=maximizing,
        stats=stats,
    )

    if maximizing:
        value = -inf
        for child in children:
            value = max(
                value,
                _search_score_ordered(
                    child,
                    participant,
                    depth - 1,
                    alpha,
                    beta,
                    stats,
                ),
            )
            alpha = max(alpha, value)
            if alpha >= beta:
                stats.cutoff_nodes += 1
                break
        return value

    value = inf
    for child in children:
        value = min(
            value,
            _search_score_ordered(
                child,
                participant,
                depth - 1,
                alpha,
                beta,
                stats,
            ),
        )
        beta = min(beta, value)
        if alpha >= beta:
            stats.cutoff_nodes += 1
            break
    return value


def choose_computer_action_score_ordered(
    state: CrownlineSet,
    participant: Participant = "B",
    *,
    depth: int = 2,
) -> tuple[str, Optional[Line], ScoreOrderedSearchStats]:
    """Choose Baseline A's action with score-only internal move ordering."""

    if depth < 1 or depth > 4:
        raise ValueError("Score-ordered search depth must be between 1 and 4")
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

    stats = ScoreOrderedSearchStats()
    ranked = []
    # Keep Baseline A's root action order and tie-breaking exactly unchanged.
    for move, meld_line in actions:
        child = state.apply_move(move, meld_line=meld_line)
        value = _search_score_ordered(
            child,
            participant,
            max(0, depth - 1),
            -inf,
            inf,
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
class ScoreOrderedBaselineEngine:
    """Benchmark adapter for Baseline A + cheap score-only move ordering."""

    name: str
    depth: int = 2
    total_expanded_nodes: int = 0
    total_cutoff_nodes: int = 0
    total_ordering_estimates: int = 0

    def __post_init__(self) -> None:
        if self.depth < 1 or self.depth > 4:
            raise ValueError("ScoreOrderedBaselineEngine depth must be between 1 and 4")

    def choose(self, state: CrownlineSet, participant: Participant) -> EngineDecision:
        root_actions = len(_actions(state))
        started = perf_counter_ns()
        notation, meld_line, stats = choose_computer_action_score_ordered(
            state,
            participant=participant,
            depth=self.depth,
        )
        elapsed_ms = (perf_counter_ns() - started) / 1_000_000.0

        self.total_expanded_nodes += stats.expanded_nodes
        self.total_cutoff_nodes += stats.cutoff_nodes
        self.total_ordering_estimates += stats.ordering_estimates

        return EngineDecision(
            notation=notation,
            meld_line=meld_line,
            elapsed_ms=elapsed_ms,
            search_nodes=stats.expanded_nodes,
            root_actions=root_actions,
        )
