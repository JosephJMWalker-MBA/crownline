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


ScorePair = tuple[int, int]  # (White total, Black total)


@dataclass
class CarriedOrderedSearchStats:
    expanded_nodes: int = 0
    cutoff_nodes: int = 0
    ordering_estimates: int = 0
    root_score_scans: int = 0


def _score_pair(state: CrownlineSet) -> ScorePair:
    game = state.current_game
    return game.score("W").total, game.score("B").total


def _child_scores_from_parent(
    state: CrownlineSet,
    child: CrownlineSet,
    move: Move,
    parent_scores: ScorePair,
) -> ScorePair:
    """Update exact W/B score totals from move-local deltas only."""

    game = state.current_game
    child_game = child.current_game
    mover = game.turn
    victim = opponent(mover)
    scores: dict[Player, int] = {"W": parent_scores[0], "B": parent_scores[1]}

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

    scores[mover] += mover_delta
    scores[victim] += victim_delta
    return scores["W"], scores["B"]


def _estimate_from_scores(
    state: CrownlineSet,
    participant: Participant,
    scores: ScorePair,
) -> float:
    """Reproduce the score-only ordering estimate from carried exact totals."""

    game = state.current_game
    my_color = state.color_for_participant(participant)
    their_color = opponent(my_color)
    by_color = {"W": scores[0], "B": scores[1]}
    score_margin = by_color[my_color] - by_color[their_color]
    if game.game_over:
        return score_margin * 1000.0

    meld_margin = len(game.melds(my_color)) - len(game.melds(their_color))
    return score_margin * 100.0 + meld_margin * 8


def _ordered_children(
    state: CrownlineSet,
    participant: Participant,
    parent_scores: ScorePair,
    *,
    maximizing: bool,
    stats: CarriedOrderedSearchStats,
) -> tuple[tuple[CrownlineSet, ScorePair], ...]:
    ranked = []
    for move, meld_line in _actions(state):
        child = state.apply_move(move, meld_line=meld_line)
        child_scores = _child_scores_from_parent(
            state,
            child,
            move,
            parent_scores,
        )
        estimate = _estimate_from_scores(child, participant, child_scores)
        stats.ordering_estimates += 1
        line_key = "-".join(meld_line) if meld_line else ""
        ranked.append((estimate, move.notation(), line_key, child, child_scores))

    if maximizing:
        ranked.sort(key=lambda item: (-item[0], item[1], item[2]))
    else:
        ranked.sort(key=lambda item: (item[0], item[1], item[2]))
    return tuple((item[3], item[4]) for item in ranked)


def _search(
    state: CrownlineSet,
    participant: Participant,
    depth: int,
    alpha: float,
    beta: float,
    scores: ScorePair,
    stats: CarriedOrderedSearchStats,
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
        scores,
        maximizing=maximizing,
        stats=stats,
    )

    if maximizing:
        value = -inf
        for child, child_scores in children:
            value = max(
                value,
                _search(
                    child,
                    participant,
                    depth - 1,
                    alpha,
                    beta,
                    child_scores,
                    stats,
                ),
            )
            alpha = max(alpha, value)
            if alpha >= beta:
                stats.cutoff_nodes += 1
                break
        return value

    value = inf
    for child, child_scores in children:
        value = min(
            value,
            _search(
                child,
                participant,
                depth - 1,
                alpha,
                beta,
                child_scores,
                stats,
            ),
        )
        beta = min(beta, value)
        if alpha >= beta:
            stats.cutoff_nodes += 1
            break
    return value


def choose_computer_action_carried_ordered(
    state: CrownlineSet,
    participant: Participant = "B",
    *,
    depth: int = 2,
) -> tuple[str, Optional[Line], CarriedOrderedSearchStats]:
    """Choose Baseline A's action while carrying exact scores through ordering."""

    if depth < 1 or depth > 4:
        raise ValueError("Carried-score ordered depth must be between 1 and 4")
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

    stats = CarriedOrderedSearchStats()
    root_scores = _score_pair(state)
    stats.root_score_scans = 1
    ranked = []
    for move, meld_line in actions:
        child = state.apply_move(move, meld_line=meld_line)
        child_scores = _child_scores_from_parent(
            state,
            child,
            move,
            root_scores,
        )
        value = _search(
            child,
            participant,
            max(0, depth - 1),
            -inf,
            inf,
            child_scores,
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
class CarriedScoreOrderedBaselineEngine:
    """Benchmark adapter for score-only ordering with recursively carried scores."""

    name: str
    depth: int = 2
    total_expanded_nodes: int = 0
    total_cutoff_nodes: int = 0
    total_ordering_estimates: int = 0
    total_root_score_scans: int = 0

    def __post_init__(self) -> None:
        if self.depth < 1 or self.depth > 4:
            raise ValueError("CarriedScoreOrderedBaselineEngine depth must be between 1 and 4")

    def choose(self, state: CrownlineSet, participant: Participant) -> EngineDecision:
        root_actions = len(_actions(state))
        started = perf_counter_ns()
        notation, meld_line, stats = choose_computer_action_carried_ordered(
            state,
            participant=participant,
            depth=self.depth,
        )
        elapsed_ms = (perf_counter_ns() - started) / 1_000_000.0

        self.total_expanded_nodes += stats.expanded_nodes
        self.total_cutoff_nodes += stats.cutoff_nodes
        self.total_ordering_estimates += stats.ordering_estimates
        self.total_root_score_scans += stats.root_score_scans

        return EngineDecision(
            notation=notation,
            meld_line=meld_line,
            elapsed_ms=elapsed_ms,
            search_nodes=stats.expanded_nodes,
            root_actions=root_actions,
        )
