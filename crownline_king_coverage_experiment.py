from __future__ import annotations

from dataclasses import dataclass
from math import inf
from time import perf_counter_ns
from typing import Optional

from crownline_ai import _actions
from crownline_benchmark import EngineDecision
from crownline_game import Line
from crownline_promotion_maturity_experiment import evaluate_with_promotion_maturity
from crownline_rules import Participant, alg_to_coord, opponent
from crownline_set import CrownlineSet


def king_unretired_line_membership_units(game, player: str) -> int:
    """Count how many unretired Crownline memberships are occupied by Kings.

    A King on an intersection contributes once for every still-unretired geometry
    that contains its square. Retired geometries contribute nothing because they
    cannot score again for that player in Crownline v1.1.

    This is deliberately a narrow *coverage* feature. It does not count ordinary
    pieces, two-of-three threats, cooldown readiness, capture safety, or future
    reachability. Those remain separate hypotheses.
    """

    retired = game.retired_lines(player)
    units = 0
    for line in game.variant.crown_lines:
        if line in retired:
            continue
        for square in line:
            piece = game.board.get(alg_to_coord(square))
            if piece is not None and piece.owner == player and piece.king:
                units += 1
    return units


def king_coverage_margin(state: CrownlineSet, participant: Participant) -> int:
    game = state.current_game
    mine = state.color_for_participant(participant)
    theirs = opponent(mine)
    return (
        king_unretired_line_membership_units(game, mine)
        - king_unretired_line_membership_units(game, theirs)
    )


def evaluate_with_king_coverage(
    state: CrownlineSet,
    participant: Participant,
    *,
    maturity_weight: float = 10.0,
    coverage_weight: float = 0.0,
) -> float:
    """Promotion-maturity evaluator plus one nonterminal King-coverage term."""

    if maturity_weight < 0:
        raise ValueError("maturity_weight must be non-negative")
    if coverage_weight < 0:
        raise ValueError("coverage_weight must be non-negative")

    baseline = evaluate_with_promotion_maturity(
        state,
        participant,
        maturity_weight=maturity_weight,
    )
    if state.current_game.game_over or coverage_weight == 0:
        return baseline
    return baseline + coverage_weight * king_coverage_margin(state, participant)


def _search_king_coverage(
    state: CrownlineSet,
    participant: Participant,
    depth: int,
    alpha: float,
    beta: float,
    *,
    maturity_weight: float,
    coverage_weight: float,
    counter: Optional[list[int]] = None,
) -> float:
    if counter is not None:
        counter[0] += 1

    game = state.current_game
    if depth <= 0 or game.game_over:
        return evaluate_with_king_coverage(
            state,
            participant,
            maturity_weight=maturity_weight,
            coverage_weight=coverage_weight,
        )

    actions = _actions(state)
    if not actions:
        return evaluate_with_king_coverage(
            state,
            participant,
            maturity_weight=maturity_weight,
            coverage_weight=coverage_weight,
        )

    maximizing = state.participant_for_color(game.turn) == participant
    if maximizing:
        value = -inf
        for move, meld_line in actions:
            child = state.apply_move(move, meld_line=meld_line)
            value = max(
                value,
                _search_king_coverage(
                    child,
                    participant,
                    depth - 1,
                    alpha,
                    beta,
                    maturity_weight=maturity_weight,
                    coverage_weight=coverage_weight,
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
            _search_king_coverage(
                child,
                participant,
                depth - 1,
                alpha,
                beta,
                maturity_weight=maturity_weight,
                coverage_weight=coverage_weight,
                counter=counter,
            ),
        )
        beta = min(beta, value)
        if alpha >= beta:
            break
    return value


def rank_king_coverage_actions(
    state: CrownlineSet,
    participant: Participant,
    *,
    depth: int = 3,
    maturity_weight: float = 10.0,
    coverage_weight: float = 0.0,
) -> list[tuple[float, str, str, Optional[Line]]]:
    if depth < 1 or depth > 4:
        raise ValueError("depth must be between 1 and 4")
    if maturity_weight < 0 or coverage_weight < 0:
        raise ValueError("weights must be non-negative")
    if state.set_over:
        raise ValueError("Set is already over")
    game = state.current_game
    if game.game_over:
        raise ValueError("Current game is already over")
    if state.participant_for_color(game.turn) != participant:
        raise ValueError(f"It is not Player {participant}'s turn")

    ranked = []
    for move, meld_line in _actions(state):
        child = state.apply_move(move, meld_line=meld_line)
        value = _search_king_coverage(
            child,
            participant,
            max(0, depth - 1),
            -inf,
            inf,
            maturity_weight=maturity_weight,
            coverage_weight=coverage_weight,
        )
        line_key = "-".join(meld_line) if meld_line else ""
        ranked.append((value, move.notation(), line_key, meld_line))

    ranked.sort(key=lambda item: (-item[0], item[1], item[2]))
    return ranked


@dataclass
class KingCoverageEngine:
    name: str
    depth: int = 3
    maturity_weight: float = 10.0
    coverage_weight: float = 0.0

    def __post_init__(self) -> None:
        if self.depth < 1 or self.depth > 4:
            raise ValueError("depth must be between 1 and 4")
        if self.maturity_weight < 0 or self.coverage_weight < 0:
            raise ValueError("weights must be non-negative")

    def choose(self, state: CrownlineSet, participant: Participant) -> EngineDecision:
        counter = [0]
        started = perf_counter_ns()
        game = state.current_game
        if state.set_over or game.game_over:
            raise ValueError("No decision is available in a terminal state")
        if state.participant_for_color(game.turn) != participant:
            raise ValueError(f"It is not Player {participant}'s turn")

        actions = _actions(state)
        ranked = []
        for move, meld_line in actions:
            child = state.apply_move(move, meld_line=meld_line)
            value = _search_king_coverage(
                child,
                participant,
                max(0, self.depth - 1),
                -inf,
                inf,
                maturity_weight=self.maturity_weight,
                coverage_weight=self.coverage_weight,
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
