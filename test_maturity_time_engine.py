from crownline_maturity_time_engine import (
    PromotionMaturityStructuralTTTimeControl,
    choose_computer_action_iterative_structural_tt_maturity,
)
from crownline_position_suite import position_suite
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


def test_zero_maturity_weight_preserves_stage2_structural_tt_policy():
    # A non-expiring fake clock forces both engines to fully complete depth 3.
    # With maturity disabled, the new engine must be exactly Stage 2.
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
            candidate = choose_computer_action_iterative_structural_tt_maturity(
                state,
                participant=participant,
                budget_ms=1.0,
                max_depth=3,
                maturity_weight=0.0,
                clock_ns=lambda: 0,
            )
            assert _label(candidate[0], candidate[1]) == _label(expected[0], expected[1])
            assert candidate[2].completed_depth == 3
            assert candidate[2].timed_out is False


def test_maturity_time_control_reports_completed_depth():
    state = _state_for_fixture(position_suite()[0].game1)
    participant = state.participant_for_color(state.current_game.turn)
    engine = PromotionMaturityStructuralTTTimeControl(
        budget_ms=1.0,
        max_depth=2,
        maturity_weight=10.0,
        clock_ns=lambda: 0,
    )
    decision = engine.choose(state, participant)

    assert decision.notation
    assert engine.decisions == 1
    assert engine.mean_completed_depth == 2.0
    assert engine.timed_out_decisions == 0


def test_maturity_time_engine_rejects_invalid_configuration():
    for kwargs in (
        {"budget_ms": 0.0},
        {"max_depth": 0},
        {"maturity_weight": -1.0},
    ):
        try:
            PromotionMaturityStructuralTTTimeControl(**kwargs)
        except ValueError:
            pass
        else:
            raise AssertionError(f"invalid configuration should fail: {kwargs}")
