from __future__ import annotations

from dataclasses import dataclass
from math import inf
from time import perf_counter_ns
from typing import Optional

from crownline_ai import _actions, _evaluate
from crownline_benchmark import EngineDecision
from crownline_game import Line
from crownline_rules import Participant, alg_to_coord, opponent
from crownline_set import CrownlineSet


def crownline_pressure_units(game, player: str) -> int:
    """Return a small, transparent measure of latent open-line structure.

    Only unretired Crownline geometries with no opponent piece on the line are
    considered.  Each owned node contributes one unit, each owned pair on the
    same open line contributes one synergy unit, and satisfying v1.1's King gate
    contributes one additional unit.

    Thus, before retirement effects:

        one ordinary piece -> 1
        one King           -> 2
        two ordinary       -> 3
        two incl. a King   -> 4
        three ordinary     -> 6
        three incl. a King -> 7

    This is deliberately geometric rather than a second scoring system. It does
    not predict exact move legality, cooldown expiry, or future captures. The
    experiment asks only whether Baseline A benefits from seeing latent
    Crownline construction/denial structure at all.
    """

    their = opponent(player)
    retired = game.retired_lines(player)
    total = 0
    for line in game.variant.crown_lines:
        if line in retired:
            continue
        pieces = tuple(game.board.get(alg_to_coord(square)) for square in line)
        if any(piece is not None and piece.owner == their for piece in pieces):
            continue
        ours = tuple(piece for piece in pieces if piece is not None and piece.owner == player)
        count = len(ours)
        if count == 0:
            continue
        total += count
        total += count * (count - 1) // 2
        if any(piece.king for piece in ours):
            total += 1
    return total


def pressure_margin(state: CrownlineSet, participant: Participant) -> int:
    game = state.current_game
    mine = state.color_for_participant(participant)
    theirs = opponent(mine)
    return crownline_pressure_units(game, mine) - crownline_pressure_units(game, theirs)


def evaluate_with_line_pressure(
    state: CrownlineSet,
    participant: Participant,
    *,
    pressure_weight: float,
) -> float:
    """Baseline A plus one nonterminal Crownline-pressure term.

    Weight zero is exactly Baseline A. Terminal positions remain exactly
    Baseline A so the experiment never changes authoritative final scoring.
    """

    if pressure_weight < 0:
        raise ValueError("pressure_weight must be non-negative")
    baseline = _evaluate(state, participant)
    if state.current_game.game_over or pressure_weight == 0:
        return baseline
    return baseline + pressure_margin(state, participant) * pressure_weight


def _search(
    state: CrownlineSet,
    participant: Participant,
    depth: int,
    alpha: float,
    beta: float,
    *,
    pressure_weight: float,
    counter: Optional[list[int]] = None,
) -> float:
    if counter is not None:
        counter[0] += 1
    game = state.current_game
    if depth <= 0 or game.game_over:
        return evaluate_with_line_pressure(
            state,
            participant,
            pressure_weight=pressure_weight,
        )
    actions = _actions(state)
    if not actions:
        return evaluate_with_line_pressure(
            state,
            participant,
            pressure_weight=pressure_weight,
        )

    maximizing = state.participant_for_color(game.turn) == participant
    if maximizing:
        value = -inf
        for move, meld_line in actions:
            child = state.apply_move(move, meld_line=meld_line)
            value = max(
                value,
                _search(
                    child,
                    participant,
                    depth - 1,
                    alpha,
                    beta,
                    pressure_weight=pressure_weight,
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
            _search(
                child,
                participant,
                depth - 1,
                alpha,
                beta,
                pressure_weight=pressure_weight,
                counter=counter,
            ),
        )
        beta = min(beta, value)
        if alpha >= beta:
            break
    return value


def choose_line_pressure_action(
    state: CrownlineSet,
    participant: Participant = "B",
    *,
    depth: int = 3,
    pressure_weight: float = 0.0,
) -> tuple[str, Optional[Line]]:
    if depth < 1 or depth > 4:
        raise ValueError("depth must be between 1 and 4")
    if pressure_weight < 0:
        raise ValueError("pressure_weight must be non-negative")
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
        value = _search(
            child,
            participant,
            max(0, depth - 1),
            -inf,
            inf,
            pressure_weight=pressure_weight,
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
class LinePressureEngine:
    name: str
    depth: int = 3
    pressure_weight: float = 0.0

    def __post_init__(self) -> None:
        if self.depth < 1 or self.depth > 4:
            raise ValueError("depth must be between 1 and 4")
        if self.pressure_weight < 0:
            raise ValueError("pressure_weight must be non-negative")

    def choose(self, state: CrownlineSet, participant: Participant) -> EngineDecision:
        root_actions = len(_actions(state))
        counter = [0]
        started = perf_counter_ns()
        actions = _actions(state)
        ranked = []
        for move, meld_line in actions:
            child = state.apply_move(move, meld_line=meld_line)
            value = _search(
                child,
                participant,
                max(0, self.depth - 1),
                -inf,
                inf,
                pressure_weight=self.pressure_weight,
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
