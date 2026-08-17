from crownline_position_suite import position_suite
from crownline_product_candidate import (
    RepeatAwareStructuralTTOpponent,
    StructuralTTTimeControl,
)
from crownline_set import CrownlineSet
from crownline_tt_time_engine import choose_computer_action_iterative_structural_tt


def _state_for_fixture(fixture) -> CrownlineSet:
    return CrownlineSet(
        first_game_white="A",
        current_game=fixture.game(),
        rules_mode="candidate",
    )


def _label(notation, meld_line):
    return notation + (f" | {'-'.join(meld_line)}" if meld_line else "")


def test_zero_repeat_penalty_preserves_stage2_structural_tt_policy():
    # With a non-expiring fake clock, both engines fully complete depth 3. A zero
    # history penalty must therefore be exactly the Stage-2 search substrate.
    for scenario in position_suite():
        for fixture in (scenario.game1, scenario.game2):
            state = _state_for_fixture(fixture)
            participant = state.participant_for_color(state.current_game.turn)
            expected = choose_computer_action_iterative_structural_tt(
                state,
                participant=participant,
                budget_ms=1.0,
                max_depth=3,
                clock_ns=lambda: 0,
            )
            candidate = RepeatAwareStructuralTTOpponent(
                budget_ms=1.0,
                max_depth=3,
                repeat_penalty=0.0,
                clock_ns=lambda: 0,
            )
            notation, meld_line, stats = candidate.choose_with_stats(state, participant)
            assert _label(notation, meld_line) == _label(expected[0], expected[1])
            assert stats.search.completed_depth == 3
            assert stats.search.timed_out is False


def test_candidate_records_actual_selected_afterstate_once_per_decision():
    state = _state_for_fixture(position_suite()[0].game1)
    participant = state.participant_for_color(state.current_game.turn)
    candidate = RepeatAwareStructuralTTOpponent(
        budget_ms=1.0,
        max_depth=2,
        repeat_penalty=50.0,
        clock_ns=lambda: 0,
    )

    notation, meld_line, stats = candidate.choose_with_stats(state, participant)

    assert notation
    assert candidate.decisions == 1
    assert candidate.memory_size == 1
    assert candidate._produced_afterstates[stats.selected_afterstate] == 1
    assert candidate.mean_completed_depth == 2.0
    assert candidate.repeated_action_selected == 0


def test_stage2_control_adapter_reports_completed_depth():
    state = _state_for_fixture(position_suite()[0].game1)
    participant = state.participant_for_color(state.current_game.turn)
    control = StructuralTTTimeControl(
        budget_ms=1.0,
        max_depth=2,
        clock_ns=lambda: 0,
    )
    decision = control.choose(state, participant)

    assert decision.notation
    assert control.decisions == 1
    assert control.mean_completed_depth == 2.0


def test_candidate_rejects_invalid_configuration():
    for kwargs in (
        {"budget_ms": 0.0},
        {"max_depth": 0},
        {"repeat_penalty": -1.0},
    ):
        try:
            RepeatAwareStructuralTTOpponent(**kwargs)
        except ValueError:
            pass
        else:
            raise AssertionError(f"invalid configuration should fail: {kwargs}")
