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
from crownline_set import CrownlineSet


def mandatory_capture_actions(state: CrownlineSet):
    """Return legal actions only when the entire turn is capture-forced.

    Crownline v1.1 Sovereignty can release a turn from mandatory capture when a
    King has a capture. In that case legal non-capturing actions coexist with
    captures, so the position is *not* considered quiescence-forced here.
    """

    actions = _actions(state)
    if not actions:
        return ()
    if all(move.is_capture for move, _ in actions):
        return actions
    return ()


def _quiescence(
    state: CrownlineSet,
    participant: Participant,
    alpha: float,
    beta: float,
    *,
    maturity_weight: float,
    qdepth: int,
    counter: Optional[list[int]] = None,
) -> float:
    if counter is not None:
        counter[0] += 1

    game = state.current_game
    if state.set_over or game.game_over or qdepth <= 0:
        return evaluate_with_promotion_maturity(
            state,
            participant,
            maturity_weight=maturity_weight,
        )

    actions = mandatory_capture_actions(state)
    if not actions:
        return evaluate_with_promotion_maturity(
            state,
            participant,
            maturity_weight=maturity_weight,
        )

    maximizing = state.participant_for_color(game.turn) == participant
    if maximizing:
        value = -inf
        for move, meld_line in actions:
            child = state.apply_move(move, meld_line=meld_line)
            value = max(
                value,
                _quiescence(
                    child,
                    participant,
                    alpha,
                    beta,
                    maturity_weight=maturity_weight,
                    qdepth=qdepth - 1,
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
            _quiescence(
                child,
                participant,
                alpha,
                beta,
                maturity_weight=maturity_weight,
                qdepth=qdepth - 1,
                counter=counter,
            ),
        )
        beta = min(beta, value)
        if alpha >= beta:
            break
    return value


def _search_quiescence(
    state: CrownlineSet,
    participant: Participant,
    depth: int,
    alpha: float,
    beta: float,
    *,
    maturity_weight: float,
    qdepth: int,
    counter: Optional[list[int]] = None,
) -> float:
    if counter is not None:
        counter[0] += 1

    game = state.current_game
    if state.set_over or game.game_over:
        return evaluate_with_promotion_maturity(
            state,
            participant,
            maturity_weight=maturity_weight,
        )
    if depth <= 0:
        if qdepth <= 0:
            return evaluate_with_promotion_maturity(
                state,
                participant,
                maturity_weight=maturity_weight,
            )
        return _quiescence(
            state,
            participant,
            alpha,
            beta,
            maturity_weight=maturity_weight,
            qdepth=qdepth,
            counter=counter,
        )

    actions = _actions(state)
    if not actions:
        return evaluate_with_promotion_maturity(
            state,
            participant,
            maturity_weight=maturity_weight,
        )

    maximizing = state.participant_for_color(game.turn) == participant
    if maximizing:
        value = -inf
        for move, meld_line in actions:
            child = state.apply_move(move, meld_line=meld_line)
            value = max(
                value,
                _search_quiescence(
                    child,
                    participant,
                    depth - 1,
                    alpha,
                    beta,
                    maturity_weight=maturity_weight,
                    qdepth=qdepth,
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
            _search_quiescence(
                child,
                participant,
                depth - 1,
                alpha,
                beta,
                maturity_weight=maturity_weight,
                qdepth=qdepth,
                counter=counter,
            ),
        )
        beta = min(beta, value)
        if alpha >= beta:
            break
    return value


def rank_quiescence_actions(
    state: CrownlineSet,
    participant: Participant,
    *,
    depth: int = 3,
    maturity_weight: float = 10.0,
    qdepth: int = 0,
) -> list[tuple[float, str, str, Optional[Line]]]:
    if depth < 1 or depth > 4:
        raise ValueError("depth must be between 1 and 4")
    if qdepth < 0:
        raise ValueError("qdepth must be non-negative")
    if maturity_weight < 0:
        raise ValueError("maturity_weight must be non-negative")
    if state.set_over or state.current_game.game_over:
        raise ValueError("No decision is available in a terminal state")
    if state.participant_for_color(state.current_game.turn) != participant:
        raise ValueError(f"It is not Player {participant}'s turn")

    ranked = []
    for move, meld_line in _actions(state):
        child = state.apply_move(move, meld_line=meld_line)
        value = _search_quiescence(
            child,
            participant,
            max(0, depth - 1),
            -inf,
            inf,
            maturity_weight=maturity_weight,
            qdepth=qdepth,
        )
        line_key = "-".join(meld_line) if meld_line else ""
        ranked.append((value, move.notation(), line_key, meld_line))
    ranked.sort(key=lambda item: (-item[0], item[1], item[2]))
    return ranked


@dataclass
class MandatoryCaptureQuiescenceEngine:
    name: str
    depth: int = 3
    maturity_weight: float = 10.0
    qdepth: int = 2

    def __post_init__(self) -> None:
        if self.depth < 1 or self.depth > 4:
            raise ValueError("depth must be between 1 and 4")
        if self.qdepth < 0:
            raise ValueError("qdepth must be non-negative")
        if self.maturity_weight < 0:
            raise ValueError("maturity_weight must be non-negative")

    def choose(self, state: CrownlineSet, participant: Participant) -> EngineDecision:
        counter = [0]
        started = perf_counter_ns()
        if state.set_over or state.current_game.game_over:
            raise ValueError("No decision is available in a terminal state")
        if state.participant_for_color(state.current_game.turn) != participant:
            raise ValueError(f"It is not Player {participant}'s turn")

        actions = _actions(state)
        ranked = []
        for move, meld_line in actions:
            child = state.apply_move(move, meld_line=meld_line)
            value = _search_quiescence(
                child,
                participant,
                max(0, self.depth - 1),
                -inf,
                inf,
                maturity_weight=self.maturity_weight,
                qdepth=self.qdepth,
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
