from crownline_ai import _actions
from crownline_delta_ordering import (
    DeltaScoreOrderedBaselineEngine,
    _delta_estimate_for_child,
)
from crownline_ordering_engines import ScoreOrderedBaselineEngine, _score_only_estimate
from crownline_position_suite import position_suite
from crownline_set import CrownlineSet


def _state_for_fixture(fixture):
    return CrownlineSet(
        first_game_white="A",
        current_game=fixture.game(),
        rules_mode="candidate",
    )


def test_delta_estimate_exactly_matches_score_only_estimate_for_every_root_action():
    for scenario in position_suite():
        for fixture in (scenario.game1, scenario.game2):
            state = _state_for_fixture(fixture)
            game = state.current_game
            participant = state.participant_for_color(game.turn)
            parent_scores = {
                "W": game.score("W").total,
                "B": game.score("B").total,
            }

            for move, meld_line in _actions(state):
                child = state.apply_move(move, meld_line=meld_line)
                delta = _delta_estimate_for_child(
                    state,
                    child,
                    move,
                    participant,
                    parent_score_by_color=parent_scores,
                )
                direct = _score_only_estimate(child, participant)
                assert delta == direct, (
                    scenario.scenario_id,
                    fixture.game().variant.number,
                    move.notation(),
                    meld_line,
                    delta,
                    direct,
                )


def test_delta_ordering_matches_score_ordering_actions_and_search_tree_depths_1_to_3():
    for depth in (1, 2, 3):
        score_ordered = ScoreOrderedBaselineEngine(f"score-d{depth}", depth=depth)
        delta_ordered = DeltaScoreOrderedBaselineEngine(f"delta-d{depth}", depth=depth)

        for scenario in position_suite():
            for fixture in (scenario.game1, scenario.game2):
                state = _state_for_fixture(fixture)
                participant = state.participant_for_color(state.current_game.turn)

                score_decision = score_ordered.choose(state, participant)
                delta_decision = delta_ordered.choose(state, participant)

                assert (delta_decision.notation, delta_decision.meld_line) == (
                    score_decision.notation,
                    score_decision.meld_line,
                )
                assert delta_decision.search_nodes == score_decision.search_nodes
                assert delta_decision.root_actions == score_decision.root_actions


def test_delta_ordering_uses_one_parent_score_scan_per_ordered_internal_node():
    scenario = next(
        item for item in position_suite() if item.scenario_id == "standard-start"
    )
    state = _state_for_fixture(scenario.game1)
    participant = state.participant_for_color(state.current_game.turn)
    engine = DeltaScoreOrderedBaselineEngine("delta-d3", depth=3)

    decision = engine.choose(state, participant)

    assert decision.search_nodes > 0
    assert engine.total_parent_score_scans > 0
    assert engine.total_ordering_estimates >= engine.total_parent_score_scans
