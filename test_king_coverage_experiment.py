from crownline_human_decision_suite import human_decision_suite
from crownline_king_coverage_experiment import (
    evaluate_with_king_coverage,
    king_unretired_line_membership_units,
)
from crownline_promotion_maturity_experiment import evaluate_with_promotion_maturity
from crownline_set import new_set


def test_initial_position_has_no_king_coverage():
    game = new_set(rules_mode="candidate").current_game
    assert king_unretired_line_membership_units(game, "W") == 0
    assert king_unretired_line_membership_units(game, "B") == 0


def test_zero_coverage_weight_is_exact_promotion_maturity_control():
    fixture = next(
        fixture
        for fixture in human_decision_suite()
        if fixture.bucket == "human-royal-sweep-preparation"
    )
    state = fixture.state()
    control = evaluate_with_promotion_maturity(
        state,
        fixture.participant,
        maturity_weight=10.0,
    )
    experimental = evaluate_with_king_coverage(
        state,
        fixture.participant,
        maturity_weight=10.0,
        coverage_weight=0.0,
    )
    assert experimental == control


def test_coverage_ignores_retired_geometries():
    fixture = next(
        fixture
        for fixture in human_decision_suite()
        if fixture.fixture_id == "human-royal-sweep-08"
    )
    game = fixture.game()
    # Seven geometries are already retired for Black immediately before the
    # eighth sweep preparation. Coverage can therefore arise only on the one
    # remaining unretired line, despite several surviving Black Kings.
    assert len(game.retired_lines("B")) == 7
    assert king_unretired_line_membership_units(game, "B") <= 3
