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


def promotion_proximity_units(game, player: str) -> float:
    """Return nonlinear ordinary-piece proximity to the promotion rank.

    A piece one rank from promotion contributes 1.0, two ranks away 0.5,
    three ranks away 1/3, and so on. Kings contribute zero because the feature
    measures unrealized promotion opportunity, not a constant King bonus.

    This deliberately does not alter Crownline's board score. It is a transparent
    nonterminal strategic feature intended to test whether Baseline A undervalues
    the approach to King authority when square-score incentives point elsewhere.
    """

    total = 0.0
    for (_, rank), piece in game.board.items():
        if piece.owner != player or piece.king:
            continue
        distance = 8 - rank if player == "W" else rank - 1
        total += 1.0 / max(1, distance)
    return total


def promotion_proximity_margin(
    state: CrownlineSet,
    participant: Participant,
) -> float:
    game = state.current_game
    mine = state.color_for_participant(participant)
    theirs = opponent(mine)
    return (
        promotion_proximity_units(game, mine)
        - promotion_proximity_units(game, theirs)
    )


def evaluate_with_promotion_proximity(
    state: CrownlineSet,
    participant: Participant,
    *,
    promotion_weight: float,
) -> float:
    """Baseline A plus one nonterminal promotion-proximity term.

    `promotion_weight=0` is exactly Baseline A. Terminal values remain exactly
    Baseline A because Crownline's authoritative final score is unchanged.
    """

    if promotion_weight < 0:
        raise ValueError("promotion_weight must be non-negative")
    baseline = _evaluate(state, participant)
    if state.current_game.game_over or promotion_weight == 0:
        return baseline
    return baseline + promotion_weight * promotion_proximity_margin(state, participant)


def _search_promotion_proximity(
    state: CrownlineSet,
    participant: Participant,
    depth: int,
    alpha: float,
    beta: float,
    *,
    promotion_weight: float,
    counter: Optional[list[int]] = None,
) -> float:
    if counter is not None:
        counter[0] += 1

    game = state.current_game
    if depth <= 0 or game.game_over:
        return evaluate_with_promotion_proximity(
            state,
            participant,
            promotion_weight=promotion_weight,
        )

    actions = _actions(state)
    if not actions:
        return evaluate_with_promotion_proximity(
            state,
            participant,
            promotion_weight=promotion_weight,
        )

    maximizing = state.participant_for_color(game.turn) == participant
    if maximizing:
        value = -inf
        for move, meld_line in actions:
            child = state.apply_move(move, meld_line=meld_line)
            value = max(
                value,
                _search_promotion_proximity(
                    child,
                    participant,
                    depth - 1,
                    alpha,
                    beta,
                    promotion_weight=promotion_weight,
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
            _search_promotion_proximity(
                child,
                participant,
                depth - 1,
                alpha,
                beta,
                promotion_weight=promotion_weight,
                counter=counter,
            ),
        )
        beta = min(beta, value)
        if alpha >= beta:
            break
    return value


def choose_promotion_proximity_action(
    state: CrownlineSet,
    participant: Participant = "B",
    *,
    depth: int = 3,
    promotion_weight: float = 0.0,
) -> tuple[str, Optional[Line]]:
    if depth < 1 or depth > 4:
        raise ValueError("depth must be between 1 and 4")
    if promotion_weight < 0:
        raise ValueError("promotion_weight must be non-negative")
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
        value = _search_promotion_proximity(
            child,
            participant,
            max(0, depth - 1),
            -inf,
            inf,
            promotion_weight=promotion_weight,
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
class PromotionProximityEngine:
    name: str
    depth: int = 3
    promotion_weight: float = 0.0

    def __post_init__(self) -> None:
        if self.depth < 1 or self.depth > 4:
            raise ValueError("depth must be between 1 and 4")
        if self.promotion_weight < 0:
            raise ValueError("promotion_weight must be non-negative")

    def choose(self, state: CrownlineSet, participant: Participant) -> EngineDecision:
        actions = _actions(state)
        if not actions:
            raise ValueError("No legal computer move is available")
        counter = [0]
        started = perf_counter_ns()
        ranked = []
        for move, meld_line in actions:
            child = state.apply_move(move, meld_line=meld_line)
            value = _search_promotion_proximity(
                child,
                participant,
                max(0, self.depth - 1),
                -inf,
                inf,
                promotion_weight=self.promotion_weight,
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
            root_actions=len(actions),
        )
