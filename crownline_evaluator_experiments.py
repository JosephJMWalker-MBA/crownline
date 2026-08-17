from __future__ import annotations

from dataclasses import dataclass
from math import inf
from time import perf_counter_ns
from typing import Optional, Tuple

from crownline_ai import _actions
from crownline_benchmark import EngineDecision
from crownline_game import Line
from crownline_rules import Participant, opponent
from crownline_set import CrownlineSet


Action = Tuple[object, Optional[Line]]


def evaluate_board_weighted(
    state: CrownlineSet,
    participant: Participant,
    *,
    board_weight: float,
) -> float:
    """Baseline A evaluator with only nonterminal board-value weight varied.

    `board_weight=1.0` is algebraically identical to Baseline A. Capture-bank
    points and already-banked Crownline bonuses retain full weight because they
    are irreversible score. Board-square value is the isolated experimental
    term because it is provisional until the game ends and can change on every
    reversible move.

    Terminal evaluation always uses the full authoritative final score,
    regardless of `board_weight`; the experiment changes only nonterminal
    guidance, never Crownline scoring rules.
    """

    if board_weight < 0:
        raise ValueError("board_weight must be non-negative")

    game = state.current_game
    my_color = state.color_for_participant(participant)
    their_color = opponent(my_color)
    mine = game.score(my_color)
    theirs = game.score(their_color)

    if game.game_over:
        return (mine.total - theirs.total) * 1000.0

    durable_margin = (
        mine.capture_bank + mine.meld_bonus
        - theirs.capture_bank - theirs.meld_bonus
    )
    board_margin = mine.board_value - theirs.board_value

    mobility = len(game.legal_moves())
    mobility_term = (
        mobility
        if state.participant_for_color(game.turn) == participant
        else -mobility
    )

    meld_term = (mine.meld_count - theirs.meld_count) * 8
    return (
        durable_margin * 100.0
        + board_margin * 100.0 * board_weight
        + meld_term
        + mobility_term
    )


def _search_board_weighted(
    state: CrownlineSet,
    participant: Participant,
    depth: int,
    alpha: float,
    beta: float,
    *,
    board_weight: float,
    counter: Optional[list[int]] = None,
) -> float:
    if counter is not None:
        counter[0] += 1

    game = state.current_game
    if depth <= 0 or game.game_over:
        return evaluate_board_weighted(
            state,
            participant,
            board_weight=board_weight,
        )

    actions = _actions(state)
    if not actions:
        return evaluate_board_weighted(
            state,
            participant,
            board_weight=board_weight,
        )

    maximizing = state.participant_for_color(game.turn) == participant
    if maximizing:
        value = -inf
        for move, meld_line in actions:
            child = state.apply_move(move, meld_line=meld_line)
            value = max(
                value,
                _search_board_weighted(
                    child,
                    participant,
                    depth - 1,
                    alpha,
                    beta,
                    board_weight=board_weight,
                    counter=counter,
                ),
            )
            alpha = max(alpha, value)
            if alpha >= beta:
                break
        return value

    value = inf
    for move, meld_line in actions:
        child = state.apply_move(move, meld_line=meld_line)
        value = min(
            value,
            _search_board_weighted(
                child,
                participant,
                depth - 1,
                alpha,
                beta,
                board_weight=board_weight,
                counter=counter,
            ),
        )
        beta = min(beta, value)
        if alpha >= beta:
            break
    return value


def choose_board_weighted_action(
    state: CrownlineSet,
    participant: Participant = "B",
    *,
    depth: int = 2,
    board_weight: float = 1.0,
) -> tuple[str, Optional[Line]]:
    """Choose a deterministic fixed-depth action under one board-value weight."""

    if depth < 1 or depth > 4:
        raise ValueError("depth must be between 1 and 4")
    if board_weight < 0:
        raise ValueError("board_weight must be non-negative")
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

    ranked = []
    for move, meld_line in actions:
        child = state.apply_move(move, meld_line=meld_line)
        value = _search_board_weighted(
            child,
            participant,
            max(0, depth - 1),
            -inf,
            inf,
            board_weight=board_weight,
        )
        line_key = "-".join(meld_line) if meld_line else ""
        ranked.append((value, move.notation(), line_key, meld_line))

    best_value = max(item[0] for item in ranked)
    best = min(
        (item for item in ranked if item[0] == best_value),
        key=lambda item: (item[1], item[2]),
    )
    return best[1], best[3]


@dataclass
class BoardWeightedEngine:
    """Benchmark adapter for the isolated nonterminal board-value experiment."""

    name: str
    depth: int = 2
    board_weight: float = 1.0

    def __post_init__(self) -> None:
        if self.depth < 1 or self.depth > 4:
            raise ValueError("depth must be between 1 and 4")
        if self.board_weight < 0:
            raise ValueError("board_weight must be non-negative")

    def choose(self, state: CrownlineSet, participant: Participant) -> EngineDecision:
        root_actions = len(_actions(state))
        counter = [0]
        started = perf_counter_ns()

        actions = _actions(state)
        ranked = []
        for move, meld_line in actions:
            child = state.apply_move(move, meld_line=meld_line)
            value = _search_board_weighted(
                child,
                participant,
                max(0, self.depth - 1),
                -inf,
                inf,
                board_weight=self.board_weight,
                counter=counter,
            )
            line_key = "-".join(meld_line) if meld_line else ""
            ranked.append((value, move.notation(), line_key, meld_line))

        best_value = max(item[0] for item in ranked)
        best = min(
            (item for item in ranked if item[0] == best_value),
            key=lambda item: (item[1], item[2]),
        )
        elapsed_ms = (perf_counter_ns() - started) / 1_000_000.0
        return EngineDecision(
            notation=best[1],
            meld_line=best[3],
            elapsed_ms=elapsed_ms,
            search_nodes=counter[0],
            root_actions=root_actions,
        )
