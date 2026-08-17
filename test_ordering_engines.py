from crownline_benchmark import BaselineEngine
from crownline_ordering_engines import ScoreOrderedBaselineEngine, _score_only_estimate
from crownline_position_suite import position_suite
from crownline_set import CrownlineSet


def _state_for_fixture(fixture):
    game = fixture.game()
    return CrownlineSet(
        first_game_white="A",
        current_game=game,
        rules_mode="candidate",
    )


def test_score_only_ordering_matches_baseline_actions_on_frozen_suite_depths_1_to_3():
    for depth in (1, 2, 3):
        baseline = BaselineEngine(f"baseline-d{depth}", depth=depth)
        ordered = ScoreOrderedBaselineEngine(f"score-ordered-d{depth}", depth=depth)
        for scenario in position_suite():
            for fixture in (scenario.game1, scenario.game2):
                state = _state_for_fixture(fixture)
                participant = state.participant_for_color(state.current_game.turn)

                baseline_decision = baseline.choose(state, participant)
                ordered_decision = ordered.choose(state, participant)

                assert (ordered_decision.notation, ordered_decision.meld_line) == (
                    baseline_decision.notation,
                    baseline_decision.meld_line,
                )
                assert ordered_decision.root_actions == baseline_decision.root_actions


def test_score_only_estimate_preserves_baseline_dominant_score_and_meld_terms():
    scenario = next(
        item for item in position_suite() if item.scenario_id == "standard-start"
    )
    state = _state_for_fixture(scenario.game1)
    participant = state.participant_for_color(state.current_game.turn)

    game = state.current_game
    my_color = state.color_for_participant(participant)
    their_color = "B" if my_color == "W" else "W"
    score_margin = game.score(my_color).total - game.score(their_color).total
    meld_margin = len(game.melds(my_color)) - len(game.melds(their_color))

    assert _score_only_estimate(state, participant) == score_margin * 100 + meld_margin * 8
