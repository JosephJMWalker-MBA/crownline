import crownline_ai

from crownline_king_position_suite import king_position_suite
from crownline_position_suite import position_suite
from crownline_promotion_utility_experiment import (
    choose_promotion_proximity_action,
    evaluate_with_promotion_proximity,
    promotion_proximity_margin,
)
from crownline_set import CrownlineSet


def _state(game) -> CrownlineSet:
    return CrownlineSet(
        first_game_white="A",
        current_game=game,
        rules_mode="candidate",
    )


def test_zero_promotion_weight_is_static_evaluator_equivalent():
    fixtures = [scenario.game1 for scenario in position_suite()[:2]]
    fixtures += list(king_position_suite()[:4])
    for fixture in fixtures:
        state = _state(fixture.game())
        for participant in ("A", "B"):
            assert evaluate_with_promotion_proximity(
                state,
                participant,
                promotion_weight=0.0,
            ) == crownline_ai._evaluate(state, participant)


def test_zero_promotion_weight_preserves_depth3_policy_on_early_and_king_suites():
    fixtures = []
    for scenario in position_suite():
        fixtures.extend((scenario.game1, scenario.game2))
    fixtures.extend(king_position_suite())

    for fixture in fixtures:
        state = _state(fixture.game())
        participant = state.participant_for_color(state.current_game.turn)
        assert choose_promotion_proximity_action(
            state,
            participant,
            depth=3,
            promotion_weight=0.0,
        ) == crownline_ai.choose_computer_action(
            state,
            participant=participant,
            depth=3,
        )


def test_promotion_margin_is_antisymmetric():
    for fixture in king_position_suite():
        state = _state(fixture.game())
        assert promotion_proximity_margin(
            state,
            "A",
        ) == -promotion_proximity_margin(state, "B")


def test_negative_promotion_weight_is_rejected():
    state = _state(position_suite()[0].game1.game())
    try:
        evaluate_with_promotion_proximity(state, "A", promotion_weight=-1.0)
    except ValueError as exc:
        assert "promotion_weight" in str(exc)
    else:
        raise AssertionError("negative promotion weight should fail")
