import crownline_ai

from crownline_game import Piece
from crownline_king_position_suite import king_position_suite
from crownline_position_suite import position_suite
from crownline_promotion_maturity_experiment import (
    choose_promotion_maturity_action,
    evaluate_with_promotion_maturity,
    piece_promotion_maturity,
    promotion_maturity_margin,
)
from crownline_set import CrownlineSet


def _state(game) -> CrownlineSet:
    return CrownlineSet(
        first_game_white="A",
        current_game=game,
        rules_mode="candidate",
    )


def test_piece_maturity_is_monotonic_and_continuous_through_crowning():
    white = Piece("W", 1)
    black = Piece("B", 1)
    white_values = [piece_promotion_maturity(white, rank) for rank in range(1, 8)]
    black_values = [piece_promotion_maturity(black, rank) for rank in range(8, 1, -1)]

    assert white_values == black_values
    assert white_values[0] == 0.0
    assert white_values[-1] == 6 / 7
    assert all(a < b for a, b in zip(white_values, white_values[1:]))

    assert piece_promotion_maturity(Piece("W", 1, king=True), 8) == 1.0
    assert piece_promotion_maturity(Piece("B", 1, king=True), 1) == 1.0
    assert 1.0 - white_values[-1] == 1 / 7


def test_king_maturity_remains_realized_endpoint_away_from_crown_rank():
    # Kings move back into the board after promotion. Their realized promotion
    # capital must not disappear when they leave the crown rank.
    for rank in range(1, 9):
        assert piece_promotion_maturity(Piece("W", 3, king=True), rank) == 1.0
        assert piece_promotion_maturity(Piece("B", 3, king=True), rank) == 1.0


def test_zero_maturity_weight_is_static_evaluator_equivalent():
    fixtures = [scenario.game1 for scenario in position_suite()[:2]]
    fixtures += list(king_position_suite()[:4])
    for fixture in fixtures:
        state = _state(fixture.game())
        for participant in ("A", "B"):
            assert evaluate_with_promotion_maturity(
                state,
                participant,
                maturity_weight=0.0,
            ) == crownline_ai._evaluate(state, participant)


def test_zero_maturity_weight_preserves_depth3_policy_on_both_guardrails():
    fixtures = []
    for scenario in position_suite():
        fixtures.extend((scenario.game1, scenario.game2))
    fixtures.extend(king_position_suite())

    for fixture in fixtures:
        state = _state(fixture.game())
        participant = state.participant_for_color(state.current_game.turn)
        assert choose_promotion_maturity_action(
            state,
            participant,
            depth=3,
            maturity_weight=0.0,
        ) == crownline_ai.choose_computer_action(
            state,
            participant=participant,
            depth=3,
        )


def test_maturity_margin_is_antisymmetric():
    for fixture in king_position_suite():
        state = _state(fixture.game())
        assert promotion_maturity_margin(
            state,
            "A",
        ) == -promotion_maturity_margin(state, "B")


def test_invalid_maturity_inputs_are_rejected():
    try:
        piece_promotion_maturity(Piece("W", 1), 0)
    except ValueError as exc:
        assert "rank" in str(exc)
    else:
        raise AssertionError("rank zero should fail")

    state = _state(position_suite()[0].game1.game())
    try:
        evaluate_with_promotion_maturity(state, "A", maturity_weight=-1.0)
    except ValueError as exc:
        assert "maturity_weight" in str(exc)
    else:
        raise AssertionError("negative maturity weight should fail")
