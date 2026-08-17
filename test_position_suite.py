import crownline as c
from crownline_position_suite import (
    POSITION_SUITE_ID,
    POSITION_SUITE_RULES_MODE,
    position_suite,
)
from crownline_state_notation import clsn_fingerprint, serialize_clsn


def test_position_suite_v0_1_is_eight_paired_v11_positions():
    scenarios = position_suite()

    assert POSITION_SUITE_ID == "v0.1"
    assert POSITION_SUITE_RULES_MODE == "candidate"
    assert len(scenarios) == 8
    assert len({scenario.scenario_id for scenario in scenarios}) == 8

    fingerprints = []
    for scenario in scenarios:
        for game_number, fixture in ((1, scenario.game1), (2, scenario.game2)):
            game = fixture.game()
            assert game.variant.number == game_number
            assert game.rules_mode == "candidate"
            assert game.game_over is False
            assert game.ply == 0
            assert serialize_clsn(game) == fixture.clsn
            assert clsn_fingerprint(game) == fixture.fingerprint
            fingerprints.append(fixture.fingerprint)

    assert len(set(fingerprints)) == 16


def test_standard_start_control_contains_both_crownline_geometries():
    control = next(
        scenario for scenario in position_suite() if scenario.scenario_id == "standard-start"
    )

    expected_game1 = c.GameState.initial(1, rules_mode="candidate")
    expected_game2 = c.GameState.initial(2, rules_mode="candidate")

    assert control.game1.clsn == serialize_clsn(expected_game1)
    assert control.game2.clsn == serialize_clsn(expected_game2)
    assert control.provenance_quantiles == ()


def test_noncontrol_pairs_are_frozen_positions_not_runtime_opening_procedures():
    scenarios = position_suite()
    noncontrols = [scenario for scenario in scenarios if scenario.scenario_id != "standard-start"]

    assert len(noncontrols) == 7
    assert all(len(scenario.provenance_quantiles) == 8 for scenario in noncontrols)
    # The quantiles remain provenance, but benchmark identity is the CLSN itself.
    assert all(scenario.game1.clsn.startswith("CLSN1|g=1|") for scenario in noncontrols)
    assert all(scenario.game2.clsn.startswith("CLSN1|g=2|") for scenario in noncontrols)
