from crownline_carried_ordering import (
    CarriedScoreOrderedBaselineEngine,
    _child_scores_from_parent,
    _estimate_from_scores,
    _score_pair,
)
from crownline_delta_ordering import DeltaScoreOrderedBaselineEngine
from crownline_ordering_engines import _score_only_estimate
from crownline_position_suite import position_suite
from crownline_set import CrownlineSet
from crownline_ai import _actions


def _state_for_fixture(fixture):
    return CrownlineSet(
        first_game_white="A",
        current_game=fixture.game(),
        rules_mode="candidate",
    )


def test_carried_scores_and_estimates_match_authoritative_child_scores_at_roots():
    for scenario in position_suite():
        for fixture in (scenario.game1, scenario.game2):
            state = _state_for_fixture(fixture)
            participant = state.participant_for_color(state.current_game.turn)
            parent_scores = _score_pair(state)

            for move, meld_line in _actions(state):
                child = state.apply_move(move, meld_line=meld_line)
                child_scores = _child_scores_from_parent(
                    state,
                    child,
                    move,
                    parent_scores,
                )
                assert child_scores == (
                    child.current_game.score("W").total,
                    child.current_game.score("B").total,
                )
                assert _estimate_from_scores(
                    child,
                    participant,
                    child_scores,
                ) == _score_only_estimate(child, participant)


def test_carried_ordering_matches_delta_ordering_actions_and_tree_depths_1_to_3():
    for depth in (1, 2, 3):
        delta = DeltaScoreOrderedBaselineEngine(f"delta-d{depth}", depth=depth)
        carried = CarriedScoreOrderedBaselineEngine(f"carried-d{depth}", depth=depth)

        for scenario in position_suite():
            for fixture in (scenario.game1, scenario.game2):
                state = _state_for_fixture(fixture)
                participant = state.participant_for_color(state.current_game.turn)

                delta_decision = delta.choose(state, participant)
                carried_decision = carried.choose(state, participant)

                assert (carried_decision.notation, carried_decision.meld_line) == (
                    delta_decision.notation,
                    delta_decision.meld_line,
                )
                assert carried_decision.search_nodes == delta_decision.search_nodes
                assert carried_decision.root_actions == delta_decision.root_actions


def test_carried_ordering_scans_scores_once_per_decision_not_once_per_internal_node():
    scenario = next(
        item for item in position_suite() if item.scenario_id == "standard-start"
    )
    state = _state_for_fixture(scenario.game1)
    participant = state.participant_for_color(state.current_game.turn)
    engine = CarriedScoreOrderedBaselineEngine("carried-d3", depth=3)

    engine.choose(state, participant)

    assert engine.total_root_score_scans == 1
    assert engine.total_ordering_estimates > 1
