from __future__ import annotations

from dataclasses import dataclass
from math import inf
from time import perf_counter_ns
from typing import Optional

from crownline_ai import _actions, _evaluate
from crownline_benchmark import EngineDecision
from crownline_game import Line, Move
from crownline_rules import Participant, Player, opponent
from crownline_set import CrownlineSet


@dataclass
class DeltaOrderedSearchStats:
    """Per-decision measurements for incremental score-only move ordering."""

    expanded_nodes: int = 0
    cutoff_nodes: int = 0
    ordering_estimates: int = 0
    parent_score_scans: int = 0


def _child_score_margin_from_parent(
    state: CrownlineSet,
    child: CrownlineSet,
    move: Move,
    participant: Participant,
    *,
    parent_score_by_color: dict[Player, int],
) -> int:
    """Compute the child's exact score margin without rescanning its board.

    Crownline's current game score is capture bank + board-square value + banked
    Crownline bonuses. For one move, those terms change only through:

    * the mover leaving one square and occupying the destination;
    * captured pieces leaving their board squares;
    * captured printed/King values entering the mover's capture bank; and
    * at most one newly banked Crownline bonus.

    Promotion, cooldown advancement, turn switching, Sovereignty, and line
    retirement do not independently alter the score total.
    """

    game = state.current_game
    child_game = child.current_game
    mover = game.turn
    victim = opponent(mover)

    mover_delta = (
        game.variant.square_value(move.path[-1])
        - game.variant.square_value(move.path[0])
    )
    victim_delta = 0
    for captured_square in move.captured:
        captured_piece = game.board[captured_square]
        mover_delta += captured_piece.capture_value()
        victim_delta -= game.variant.square_value(captured_square)

    before_meld_count = len(game.melds(mover))
    after_melds = child_game.melds(mover)
    if len(after_melds) > before_meld_count:
        mover_delta += sum(
            meld.points for meld in after_melds[before_meld_count:]
        )

    child_score = dict(parent_score_by_color)
    child_score[mover] += mover_delta
    child_score[victim] += victim_delta

    my_color = state.color_for_participant(participant)
    their_color = opponent(my_color)
    return child_score[my_color] - child_score[their_color]


def _delta_estimate_for_child(
    state: CrownlineSet,
    child: CrownlineSet,
    move: Move,
    participant: Participant,
    *,
    parent_score_by_color: dict[Player, int],
) -> float:
    """Reproduce score-only ordering exactly using parent score + move deltas."""

    score_margin = _child_score_margin_from_parent(
        state,
        child,
        move,
        participant,
        parent_score_by_color=parent_score_by_color,
    )
    child_game = child.current_game
    if child_game.game_over:
        return score_margin * 1000.0

    my_color = state.color_for_participant(participant)
    their_color = opponent(my_color)
    meld_margin = len(child_game.melds(my_color)) - len(child_game.melds(their_color))
    return score_margin * 100.0 + meld_margin * 8


def _delta_ordered_children(
    state: CrownlineSet,
    participant: Participant,
    *,
    maximizing: bool,
    stats: DeltaOrderedSearchStats,
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


def _search_delta_ordered(
    state: CrownlineSet,
    participant: Participant,
    depth: int,
    alpha: float,
    beta: float,
    stats: DeltaOrderedSearchStats,
) -> float:
    stats.expanded_nodes += 1
    game = state.current_game
    if depth <= 0 or game.game_over:
        return _evaluate(state, participant)

    actions = _actions(state)
    if not actions:
        return _evaluate(state, participant)

    maximizing = state.participant_for_color(game.turn) == participant
    children = _delta_ordered_children(
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
                _search_delta_ordered(
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
            _search_delta_ordered(
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


def choose_computer_action_delta_ordered(
    state: CrownlineSet,
    participant: Participant = "B",
    *,
    depth: int = 2,
) -> tuple[str, Optional[Line], DeltaOrderedSearchStats]:
    """Choose Baseline A's action with delta-equivalent score-only ordering."""

    if depth < 1 or depth > 4:
        raise ValueError("Delta-ordered search depth must be between 1 and 4")
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

    stats = DeltaOrderedSearchStats()
    ranked = []
    # Root remains Baseline A order. Ordering is an internal traversal concern.
    for move, meld_line in actions:
        child = state.apply_move(move, meld_line=meld_line)
        value = _search_delta_ordered(
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
class DeltaScoreOrderedBaselineEngine:
    """Benchmark adapter for delta-equivalent score-only move ordering."""

    name: str
    depth: int = 2
    total_expanded_nodes: int = 0
    total_cutoff_nodes: int = 0
    total_ordering_estimates: int = 0
    total_parent_score_scans: int = 0

    def __post_init__(self) -> None:
        if self.depth < 1 or self.depth > 4:
            raise ValueError("DeltaScoreOrderedBaselineEngine depth must be between 1 and 4")

    def choose(self, state: CrownlineSet, participant: Participant) -> EngineDecision:
        root_actions = len(_actions(state))
        started = perf_counter_ns()
        notation, meld_line, stats = choose_computer_action_delta_ordered(
            state,
            participant=participant,
            depth=self.depth,
        )
        elapsed_ms = (perf_counter_ns() - started) / 1_000_000.0

        self.total_expanded_nodes += stats.expanded_nodes
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
