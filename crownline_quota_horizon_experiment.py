from __future__ import annotations

from dataclasses import dataclass
from math import inf
from time import perf_counter_ns
from typing import Optional

from crownline_ai import _actions, _evaluate
from crownline_benchmark import EngineDecision
from crownline_game import Line
from crownline_rules import Participant
from crownline_set import CrownlineSet


def quota_horizon_search(
    state: CrownlineSet,
    participant: Participant,
    depth: int,
    alpha: float,
    beta: float,
    *,
    extend_final_response: bool = True,
    counter: Optional[list[int]] = None,
    extension_counter: Optional[list[int]] = None,
) -> float:
    """Baseline minimax with one exact Crownline-specific horizon extension.

    Crownline's capture quota does not end a game immediately. The opponent gets
    exactly one final response turn. Baseline A's ordinary depth cutoff can land
    on the state *between* those two events: `triggering_player` is set, but the
    final response has not yet been resolved. At that leaf Baseline A applies an
    ordinary nonterminal static evaluation even though the game has exactly one
    legal turn remaining.

    When enabled, this experiment resolves that forced final-response turn before
    evaluating the leaf. No other leaf is extended; the static evaluator, legal
    moves, alpha-beta semantics, and terminal scoring remain unchanged.

    This is a search-horizon correction, not a Crownline rule and not a new
    strategic scoring term.
    """

    if counter is not None:
        counter[0] += 1

    game = state.current_game
    if game.game_over:
        return _evaluate(state, participant)

    forced_extension = (
        extend_final_response
        and depth <= 0
        and game.triggering_player is not None
    )
    if depth <= 0 and not forced_extension:
        return _evaluate(state, participant)

    if forced_extension and extension_counter is not None:
        extension_counter[0] += 1

    actions = _actions(state)
    if not actions:
        return _evaluate(state, participant)

    maximizing = state.participant_for_color(game.turn) == participant
    next_depth = depth - 1 if depth > 0 else 0

    if maximizing:
        value = -inf
        for move, meld_line in actions:
            child = state.apply_move(move, meld_line=meld_line)
            value = max(
                value,
                quota_horizon_search(
                    child,
                    participant,
                    next_depth,
                    alpha,
                    beta,
                    extend_final_response=extend_final_response,
                    counter=counter,
                    extension_counter=extension_counter,
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
            quota_horizon_search(
                child,
                participant,
                next_depth,
                alpha,
                beta,
                extend_final_response=extend_final_response,
                counter=counter,
                extension_counter=extension_counter,
            ),
        )
        beta = min(beta, value)
        if alpha >= beta:
            break
    return value


def choose_quota_horizon_action(
    state: CrownlineSet,
    participant: Participant = "B",
    *,
    depth: int = 3,
    extend_final_response: bool = True,
) -> tuple[str, Optional[Line]]:
    if depth < 1 or depth > 4:
        raise ValueError("depth must be between 1 and 4")
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
        value = quota_horizon_search(
            child,
            participant,
            max(0, depth - 1),
            -inf,
            inf,
            extend_final_response=extend_final_response,
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
class QuotaHorizonEngine:
    name: str
    depth: int = 3
    extend_final_response: bool = True
    extended_leaf_states: int = 0

    def __post_init__(self) -> None:
        if self.depth < 1 or self.depth > 4:
            raise ValueError("depth must be between 1 and 4")

    def choose(self, state: CrownlineSet, participant: Participant) -> EngineDecision:
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

        counter = [0]
        extension_counter = [0]
        started = perf_counter_ns()
        ranked = []
        for move, meld_line in actions:
            child = state.apply_move(move, meld_line=meld_line)
            value = quota_horizon_search(
                child,
                participant,
                max(0, self.depth - 1),
                -inf,
                inf,
                extend_final_response=self.extend_final_response,
                counter=counter,
                extension_counter=extension_counter,
            )
            line_key = "-".join(meld_line) if meld_line else ""
            ranked.append((value, move.notation(), line_key, meld_line))

        best_value = max(item[0] for item in ranked)
        best = min(
            (item for item in ranked if item[0] == best_value),
            key=lambda item: (item[1], item[2]),
        )
        self.extended_leaf_states += extension_counter[0]

        elapsed_ms = (perf_counter_ns() - started) / 1_000_000.0
        return EngineDecision(
            notation=best[1],
            meld_line=best[3],
            elapsed_ms=elapsed_ms,
            search_nodes=counter[0],
            root_actions=len(actions),
        )
