from __future__ import annotations

from dataclasses import dataclass
from math import inf
from time import perf_counter_ns
from typing import Optional

from crownline_ai import _actions, _evaluate
from crownline_benchmark import EngineDecision
from crownline_game import Line, Piece
from crownline_rules import Participant, opponent
from crownline_set import CrownlineSet


def piece_promotion_maturity(piece: Piece, rank: int) -> float:
    """Return a continuous realized/unrealized promotion value in [0, 1].

    Ordinary pieces rise linearly toward promotion. Existing Kings remain at the
    realized endpoint 1.0, so crowning has no value cliff:

        White rank 1..7 -> 0/7 .. 6/7 -> King 1
        Black rank 8..2 -> 0/7 .. 6/7 -> King 1

    The feature is deliberately narrow. It represents promotion capital only;
    it does not attempt to value King mobility, Crownline geometry, Sovereignty,
    or capture liability.
    """

    if rank < 1 or rank > 8:
        raise ValueError("rank must be between 1 and 8")
    if piece.king:
        return 1.0
    progress = rank - 1 if piece.owner == "W" else 8 - rank
    return max(0.0, min(6.0, float(progress))) / 7.0


def promotion_maturity_units(game, player: str) -> float:
    return sum(
        piece_promotion_maturity(piece, rank)
        for (_, rank), piece in game.board.items()
        if piece.owner == player
    )


def promotion_maturity_margin(
    state: CrownlineSet,
    participant: Participant,
) -> float:
    game = state.current_game
    mine = state.color_for_participant(participant)
    theirs = opponent(mine)
    return promotion_maturity_units(game, mine) - promotion_maturity_units(game, theirs)


def evaluate_with_promotion_maturity(
    state: CrownlineSet,
    participant: Participant,
    *,
    maturity_weight: float,
) -> float:
    """Baseline A plus one nonterminal continuous promotion-capital term."""

    if maturity_weight < 0:
        raise ValueError("maturity_weight must be non-negative")
    baseline = _evaluate(state, participant)
    if state.current_game.game_over or maturity_weight == 0:
        return baseline
    return baseline + maturity_weight * promotion_maturity_margin(state, participant)


def _search_promotion_maturity(
    state: CrownlineSet,
    participant: Participant,
    depth: int,
    alpha: float,
    beta: float,
    *,
    maturity_weight: float,
    counter: Optional[list[int]] = None,
) -> float:
    if counter is not None:
        counter[0] += 1

    game = state.current_game
    if depth <= 0 or game.game_over:
        return evaluate_with_promotion_maturity(
            state,
            participant,
            maturity_weight=maturity_weight,
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
                _search_promotion_maturity(
                    child,
                    participant,
                    depth - 1,
                    alpha,
                    beta,
                    maturity_weight=maturity_weight,
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
            _search_promotion_maturity(
                child,
                participant,
                depth - 1,
                alpha,
                beta,
                maturity_weight=maturity_weight,
                counter=counter,
            ),
        )
        beta = min(beta, value)
        if alpha >= beta:
            break
    return value


def choose_promotion_maturity_action(
    state: CrownlineSet,
    participant: Participant = "B",
    *,
    depth: int = 3,
    maturity_weight: float = 0.0,
) -> tuple[str, Optional[Line]]:
    if depth < 1 or depth > 4:
        raise ValueError("depth must be between 1 and 4")
    if maturity_weight < 0:
        raise ValueError("maturity_weight must be non-negative")
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
        value = _search_promotion_maturity(
            child,
            participant,
            max(0, depth - 1),
            -inf,
            inf,
            maturity_weight=maturity_weight,
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
class PromotionMaturityEngine:
    name: str
    depth: int = 3
    maturity_weight: float = 0.0

    def __post_init__(self) -> None:
        if self.depth < 1 or self.depth > 4:
            raise ValueError("depth must be between 1 and 4")
        if self.maturity_weight < 0:
            raise ValueError("maturity_weight must be non-negative")

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
        started = perf_counter_ns()
        ranked = []
        for move, meld_line in actions:
            child = state.apply_move(move, meld_line=meld_line)
            value = _search_promotion_maturity(
                child,
                participant,
                max(0, self.depth - 1),
                -inf,
                inf,
                maturity_weight=self.maturity_weight,
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
