from crownline_maturity_product_candidate import RepeatAwareMaturityStructuralTTOpponent
from crownline_maturity_time_engine import choose_computer_action_iterative_structural_tt_maturity
from crownline_position_suite import position_suite
from crownline_product_candidate import RepeatAwareStructuralTTOpponent
from crownline_set import CrownlineSet


def _state_for_fixture(fixture) -> CrownlineSet:
    return CrownlineSet(
        first_game_white="A",
        current_game=fixture.game(),
        rules_mode="candidate",
    )


def _label(notation, meld_line):
    return notation + (f" | {'-'.join(meld_line)}" if meld_line else "")


def test_zero_repeat_penalty_preserves_maturity_time_search():
    for scenario in position_suite():
        for fixture in (scenario.game1, scenario.game2):
            state = _state_for_fixture(fixture)
            participant = state.participant_for_color(state.current_game.turn)
            expected = choose_computer_action_iterative_structural_tt_maturity(
                state,
                participant=participant,
                budget_ms=1.0,
                max_depth=3,
                maturity_weight=10.0,
                clock_ns=lambda: 0,
            )
            composed = RepeatAwareMaturityStructuralTTOpponent(
                budget_ms=1.0,
                max_depth=3,
                repeat_penalty=0.0,
                maturity_weight=10.0,
                clock_ns=lambda: 0,
            )
            notation, meld_line, stats = composed.choose_with_stats(state, participant)
            assert _label(notation, meld_line) == _label(expected[0], expected[1])
            assert stats.search.completed_depth == 3
            assert stats.search.timed_out is False


def test_zero_maturity_preserves_p200_product_search_on_first_visit():
    for scenario in position_suite():
        for fixture in (scenario.game1, scenario.game2):
            state = _state_for_fixture(fixture)
            participant = state.participant_for_color(state.current_game.turn)
            expected = RepeatAwareStructuralTTOpponent(
                budget_ms=1.0,
                max_depth=3,
                repeat_penalty=200.0,
                clock_ns=lambda: 0,
            )
            composed = RepeatAwareMaturityStructuralTTOpponent(
                budget_ms=1.0,
                max_depth=3,
                repeat_penalty=200.0,
                maturity_weight=0.0,
                clock_ns=lambda: 0,
            )
            expected_decision = expected.choose(state, participant)
            composed_decision = composed.choose(state, participant)
            assert _label(expected_decision.notation, expected_decision.meld_line) == _label(
                composed_decision.notation,
                composed_decision.meld_line,
            )


def test_composed_candidate_records_selected_afterstate():
    state = _state_for_fixture(position_suite()[0].game1)
    participant = state.participant_for_color(state.current_game.turn)
    engine = RepeatAwareMaturityStructuralTTOpponent(
        budget_ms=1.0,
        max_depth=2,
        repeat_penalty=200.0,
        maturity_weight=10.0,
        clock_ns=lambda: 0,
    )
    notation, _, stats = engine.choose_with_stats(state, participant)

    assert notation
    assert engine.decisions == 1
    assert engine.memory_size == 1
    assert engine._produced_afterstates[stats.selected_afterstate] == 1
    assert engine.mean_completed_depth == 2.0


def test_composed_candidate_rejects_invalid_configuration():
    for kwargs in (
        {"budget_ms": 0.0},
        {"max_depth": 0},
        {"repeat_penalty": -1.0},
        {"maturity_weight": -1.0},
    ):
        try:
            RepeatAwareMaturityStructuralTTOpponent(**kwargs)
        except ValueError:
            pass
        else:
            raise AssertionError(f"invalid configuration should fail: {kwargs}")
