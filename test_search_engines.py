from crownline_benchmark import BaselineEngine
from crownline_position_suite import position_suite
from crownline_search_engines import (
    ExactStructuralTTBaselineEngine,
    ExactTTBaselineEngine,
    TranspositionSearchStats,
    _structural_tt_key,
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


def test_structural_tt_matches_clsn_tt_actions_and_search_counts_at_depth3():
    for scenario in position_suite():
        for fixture in (scenario.game1, scenario.game2):
            state = _state_for_fixture(fixture)
            participant = state.participant_for_color(state.current_game.turn)
            clsn_tt = ExactTTBaselineEngine("clsn-tt-d3", depth=3)
            structural_tt = ExactStructuralTTBaselineEngine("structural-tt-d3", depth=3)

            clsn_decision = clsn_tt.choose(state, participant)
            structural_decision = structural_tt.choose(state, participant)

            assert (structural_decision.notation, structural_decision.meld_line) == (
                clsn_decision.notation,
                clsn_decision.meld_line,
            )
            assert structural_decision.search_nodes == clsn_decision.search_nodes
            assert structural_tt.total_cache_hits == clsn_tt.total_cache_hits
            assert structural_tt.total_exact_entries == clsn_tt.total_exact_entries
            assert structural_tt.total_cutoff_nodes == clsn_tt.total_cutoff_nodes


def test_tt_keys_include_participant_mapping_and_search_perspective():
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

    for key_builder in (_tt_key, _structural_tt_key):
        assert key_builder(a_first, "A", 3) != key_builder(b_first, "A", 3)
        assert key_builder(a_first, "A", 3) != key_builder(a_first, "B", 3)
        assert key_builder(a_first, "A", 3) != key_builder(a_first, "A", 2)


def test_structural_key_changes_when_clsn_position_identity_changes():
    scenario = next(
        item for item in position_suite() if item.scenario_id == "standard-start"
    )
    state = _state_for_fixture(scenario.game1)
    participant = state.participant_for_color(state.current_game.turn)
    legal_move = state.current_game.legal_moves()[0]
    child = state.apply_move(legal_move)

    assert _tt_key(state, participant, 3) != _tt_key(child, participant, 3)
    assert _structural_tt_key(state, participant, 3) != _structural_tt_key(
        child,
        participant,
        3,
    )


def test_transposition_stats_define_hits_as_avoided_expansions():
    stats = TranspositionSearchStats(expanded_nodes=8, cache_hits=2)

    assert stats.probes == 10
    assert stats.hit_rate == 0.2
