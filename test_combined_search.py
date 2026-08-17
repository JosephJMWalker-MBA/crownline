from crownline_benchmark import BaselineEngine
from crownline_combined_search import ScoreOrderedStructuralTTBaselineEngine
from crownline_ordering_engines import ScoreOrderedBaselineEngine
from crownline_position_suite import position_suite
from crownline_set import CrownlineSet


def _state_for_fixture(fixture):
    return CrownlineSet(
        first_game_white="A",
        current_game=fixture.game(),
        rules_mode="candidate",
    )


def test_score_ordered_structural_tt_matches_baseline_actions_depths_1_to_3():
    for depth in (1, 2, 3):
        baseline = BaselineEngine(f"baseline-d{depth}", depth=depth)
        combined = ScoreOrderedStructuralTTBaselineEngine(
            f"score-ordered-tt-d{depth}",
            depth=depth,
        )
        for scenario in position_suite():
            for fixture in (scenario.game1, scenario.game2):
                state = _state_for_fixture(fixture)
                participant = state.participant_for_color(state.current_game.turn)

                baseline_decision = baseline.choose(state, participant)
                combined_decision = combined.choose(state, participant)

                assert (combined_decision.notation, combined_decision.meld_line) == (
                    baseline_decision.notation,
                    baseline_decision.meld_line,
                )
                assert combined_decision.root_actions == baseline_decision.root_actions


def test_adding_tt_to_score_ordering_never_increases_expanded_nodes_on_frozen_suite_d3():
    score_only = ScoreOrderedBaselineEngine("score-only-d3", depth=3)
    combined = ScoreOrderedStructuralTTBaselineEngine("score-tt-d3", depth=3)

    for scenario in position_suite():
        for fixture in (scenario.game1, scenario.game2):
            state = _state_for_fixture(fixture)
            participant = state.participant_for_color(state.current_game.turn)

            score_decision = score_only.choose(state, participant)
            combined_decision = combined.choose(state, participant)

            assert combined_decision.search_nodes <= score_decision.search_nodes
