from crownline_benchmark import BaselineEngine
from crownline_position_suite import position_suite
from crownline_search_engines import (
    ExactTTBaselineEngine,
    TranspositionSearchStats,
    _tt_key,
)
from crownline_set import CrownlineSet


def _state_for_fixture(fixture):
    game = fixture.game()
    return CrownlineSet(
        first_game_white="A",
        current_game=game,
        rules_mode="candidate",
    )


def test_exact_tt_matches_baseline_actions_across_frozen_suite_at_depths_1_to_3():
    for depth in (1, 2, 3):
        baseline = BaselineEngine(f"baseline-d{depth}", depth=depth)
        for scenario in position_suite():
            for fixture in (scenario.game1, scenario.game2):
                state = _state_for_fixture(fixture)
                participant = state.participant_for_color(state.current_game.turn)
                tt = ExactTTBaselineEngine(f"exact-tt-d{depth}", depth=depth)

                baseline_decision = baseline.choose(state, participant)
                tt_decision = tt.choose(state, participant)

                assert (tt_decision.notation, tt_decision.meld_line) == (
                    baseline_decision.notation,
                    baseline_decision.meld_line,
                )
                assert tt_decision.root_actions == baseline_decision.root_actions
                assert tt_decision.search_nodes >= 0


def test_tt_key_includes_participant_mapping_not_just_clsn():
    scenario = next(
        item for item in position_suite() if item.scenario_id == "standard-start"
    )
    game = scenario.game1.game()
    a_first = CrownlineSet(
        first_game_white="A",
        current_game=game,
        rules_mode="candidate",
    )
    b_first = CrownlineSet(
        first_game_white="B",
        current_game=game,
        rules_mode="candidate",
    )

    assert _tt_key(a_first, "A", 3) != _tt_key(b_first, "A", 3)
    assert _tt_key(a_first, "A", 3) != _tt_key(a_first, "B", 3)
    assert _tt_key(a_first, "A", 3) != _tt_key(a_first, "A", 2)


def test_transposition_stats_define_hits_as_avoided_expansions():
    stats = TranspositionSearchStats(expanded_nodes=8, cache_hits=2)

    assert stats.probes == 10
    assert stats.hit_rate == 0.2
