from dataclasses import replace

import crownline_ai
from crownline_evaluator_experiments import (
    choose_board_weighted_action,
    evaluate_board_weighted,
)
from crownline_position_suite import position_suite
from crownline_set import CrownlineSet


def _state_for_fixture(fixture) -> CrownlineSet:
    return CrownlineSet(
        first_game_white="A",
        current_game=fixture.game(),
        rules_mode="candidate",
    )


def test_board_weight_one_is_static_evaluator_equivalent_on_frozen_suite():
    for scenario in position_suite():
        for fixture in (scenario.game1, scenario.game2):
            state = _state_for_fixture(fixture)
            participant = state.participant_for_color(state.current_game.turn)
            assert evaluate_board_weighted(
                state,
                participant,
                board_weight=1.0,
            ) == crownline_ai._evaluate(state, participant)


def test_board_weight_one_preserves_depth2_policy_on_frozen_suite():
    for scenario in position_suite():
        for fixture in (scenario.game1, scenario.game2):
            state = _state_for_fixture(fixture)
            participant = state.participant_for_color(state.current_game.turn)
            assert choose_board_weighted_action(
                state,
                participant,
                depth=2,
                board_weight=1.0,
            ) == crownline_ai.choose_computer_action(
                state,
                participant=participant,
                depth=2,
            )


def test_terminal_score_is_full_and_independent_of_board_weight():
    fixture = position_suite()[0].game1
    state = _state_for_fixture(fixture)
    terminal = replace(
        state,
        current_game=replace(
            state.current_game,
            game_over=True,
            end_reason="test_terminal",
        ),
    )
    participant = terminal.participant_for_color(terminal.current_game.turn)
    assert evaluate_board_weighted(terminal, participant, board_weight=0.0) == evaluate_board_weighted(
        terminal,
        participant,
        board_weight=1.0,
    )


def test_negative_board_weight_is_rejected():
    fixture = position_suite()[0].game1
    state = _state_for_fixture(fixture)
    participant = state.participant_for_color(state.current_game.turn)
    try:
        evaluate_board_weighted(state, participant, board_weight=-0.1)
    except ValueError as exc:
        assert "board_weight" in str(exc)
    else:
        raise AssertionError("negative board weight should be rejected")
