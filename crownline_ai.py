from __future__ import annotations

from math import inf
from typing import Optional, Tuple

from crownline_game import Line, Move
from crownline_rules import Participant, opponent
from crownline_set import CrownlineSet


Action = Tuple[Move, Optional[Line]]


def _actions(state: CrownlineSet) -> Tuple[Action, ...]:
    """Enumerate legal move + meld-choice actions without mutating state."""
    actions = []
    game = state.current_game
    for move in game.legal_moves():
        melds = game.meld_options_after(move)
        if len(melds) > 1:
            actions.extend((move, meld.line) for meld in melds)
        else:
            actions.append((move, melds[0].line if melds else None))
    return tuple(actions)


def _evaluate(state: CrownlineSet, participant: Participant) -> float:
    """Static evaluation from one participant's perspective.

    The engine deliberately uses only authoritative game state. The weighting is
    modest: current mathematical score dominates, then mobility breaks close
    positions. This is a playable opponent, not a claim of solved strategy.
    """
    game = state.current_game
    my_color = state.color_for_participant(participant)
    their_color = opponent(my_color)
    score_margin = game.score(my_color).total - game.score(their_color).total

    if game.game_over:
        return score_margin * 1000.0

    mobility = len(game.legal_moves())
    mobility_term = mobility if state.participant_for_color(game.turn) == participant else -mobility

    my_melds = len(game.melds(my_color))
    their_melds = len(game.melds(their_color))
    meld_term = (my_melds - their_melds) * 8

    return score_margin * 100.0 + meld_term + mobility_term


def _search(state: CrownlineSet, participant: Participant, depth: int, alpha: float, beta: float) -> float:
    game = state.current_game
    if depth <= 0 or game.game_over:
        return _evaluate(state, participant)

    actions = _actions(state)
    if not actions:
        return _evaluate(state, participant)

    maximizing = state.participant_for_color(game.turn) == participant

    if maximizing:
        value = -inf
        for move, meld_line in actions:
            child = state.apply_move(move, meld_line=meld_line)
            value = max(value, _search(child, participant, depth - 1, alpha, beta))
            alpha = max(alpha, value)
            if alpha >= beta:
                break
        return value

    value = inf
    for move, meld_line in actions:
        child = state.apply_move(move, meld_line=meld_line)
        value = min(value, _search(child, participant, depth - 1, alpha, beta))
        beta = min(beta, value)
        if alpha >= beta:
            break
    return value


def choose_computer_action(
    state: CrownlineSet,
    participant: Participant = "B",
    *,
    depth: int = 2,
) -> Tuple[str, Optional[Line]]:
    """Choose a deterministic computer action for the participant whose turn it is.

    Search depth 2 is intentionally lightweight so the dependency-free local web
    server stays responsive. Lexicographic notation breaks equal evaluations.
    """
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
        value = _search(child, participant, max(0, depth - 1), -inf, inf)
        line_key = "-".join(meld_line) if meld_line else ""
        ranked.append((value, move.notation(), line_key, meld_line))

    best_value = max(item[0] for item in ranked)
    best = min(
        (item for item in ranked if item[0] == best_value),
        key=lambda item: (item[1], item[2]),
    )
    return best[1], best[3]
