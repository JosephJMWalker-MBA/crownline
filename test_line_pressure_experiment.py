from dataclasses import replace

import crownline_ai

from crownline_line_pressure_experiment import (
    choose_line_pressure_action,
    crownline_pressure_units,
    evaluate_with_line_pressure,
)
from crownline_position_suite import position_suite
from crownline_set import CrownlineSet
from crownline_state_notation import parse_clsn


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
    # Use a preserved v1.1 state whose Black b4-d4-f4 geometry has already
    # scored. If that meld is removed from history, the same two Black pieces
    # form a live open pair and must increase geometric pressure.
    game = parse_clsn(
        "CLSN1|g=1|r=candidate|t=W|b=6,7|q=-|o=0|e=-|"
        "p=a5:W3,b4:B1K,b6:W6,d4:B3,d6:W5K,g5:B5K,h4:B6|"
        "mw=-|mb=b4.d4.f4:5.3.1:15:0|cw=-|cb=-"
    )
    assert ("b4", "d4", "f4") in game.retired_lines("B")
    retired_pressure = crownline_pressure_units(game, "B")
    unretired = replace(game, melds_b=())
    live_pressure = crownline_pressure_units(unretired, "B")
    assert live_pressure == retired_pressure + 4


def test_negative_pressure_weight_is_rejected():
    state = _state_for_fixture(position_suite()[0].game1)
    participant = state.participant_for_color(state.current_game.turn)
    try:
        evaluate_with_line_pressure(state, participant, pressure_weight=-1.0)
    except ValueError as exc:
        assert "pressure_weight" in str(exc)
    else:
        raise AssertionError("negative pressure weight should be rejected")
