from crownline_combined_search import ScoreOrderedStructuralTTBaselineEngine
from crownline_delta_tt import DeltaScoreOrderedStructuralTTBaselineEngine
from crownline_position_suite import position_suite
from crownline_set import CrownlineSet


def _state_for_fixture(fixture):
    return CrownlineSet(
        first_game_white="A",
        current_game=fixture.game(),
        rules_mode="candidate",
    )


def test_delta_tt_matches_prior_combined_actions_nodes_and_hits_depths_1_to_3():
    for depth in (1, 2, 3):
        score_tt = ScoreOrderedStructuralTTBaselineEngine(
            f"score-tt-d{depth}",
            depth=depth,
        )
        delta_tt = DeltaScoreOrderedStructuralTTBaselineEngine(
            f"delta-tt-d{depth}",
            depth=depth,
        )

        for scenario in position_suite():
            for fixture in (scenario.game1, scenario.game2):
                state = _state_for_fixture(fixture)
                participant = state.participant_for_color(state.current_game.turn)
                score_hits_before = score_tt.total_cache_hits
                delta_hits_before = delta_tt.total_cache_hits

                score_decision = score_tt.choose(state, participant)
                delta_decision = delta_tt.choose(state, participant)

                assert (delta_decision.notation, delta_decision.meld_line) == (
                    score_decision.notation,
                    score_decision.meld_line,
                )
                assert delta_decision.search_nodes == score_decision.search_nodes
                assert (
                    delta_tt.total_cache_hits - delta_hits_before
                    == score_tt.total_cache_hits - score_hits_before
                )
                assert delta_decision.root_actions == score_decision.root_actions
