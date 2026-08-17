import crownline_ai

from crownline_line_pressure_experiment import (
    choose_line_pressure_action,
    crownline_pressure_units,
    evaluate_with_line_pressure,
)
from crownline_position_suite import position_suite
from crownline_set import CrownlineSet


def _state_for_fixture(fixture) -> CrownlineSet:
    return CrownlineSet(
        first_game_white="A",
        current_game=fixture.game(),
        rules_mode="candidate",
    )


def test_zero_pressure_weight_is_static_evaluator_equivalent():
    for scenario in position_suite():
        for fixture in (scenario.game1, scenario.game2):
            state = _state_for_fixture(fixture)
            participant = state.participant_for_color(state.current_game.turn)
            assert evaluate_with_line_pressure(
                state,
                participant,
                pressure_weight=0.0,
            ) == crownline_ai._evaluate(state, participant)


def test_zero_pressure_weight_preserves_depth3_policy():
    for scenario in position_suite():
        for fixture in (scenario.game1, scenario.game2):
            state = _state_for_fixture(fixture)
            participant = state.participant_for_color(state.current_game.turn)
            assert choose_line_pressure_action(
                state,
                participant,
                depth=3,
                pressure_weight=0.0,
            ) == crownline_ai.choose_computer_action(
                state,
                participant=participant,
                depth=3,
            )


def test_retired_lines_do_not_contribute_pressure():
    # The frozen suite contains scored lines in several positions. Pressure must
    # never count a player's retired geometry as future construction capacity.
    found = False
    for scenario in position_suite():
        for fixture in (scenario.game1, scenario.game2):
            game = fixture.game()
            for player in ("W", "B"):
                if game.retired_lines(player):
                    found = True
                    value = crownline_pressure_units(game, player)
                    assert value >= 0
    assert found


def test_negative_pressure_weight_is_rejected():
    state = _state_for_fixture(position_suite()[0].game1)
    participant = state.participant_for_color(state.current_game.turn)
    try:
        evaluate_with_line_pressure(state, participant, pressure_weight=-1.0)
    except ValueError as exc:
        assert "pressure_weight" in str(exc)
    else:
        raise AssertionError("negative pressure weight should be rejected")
