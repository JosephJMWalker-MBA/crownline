from collections import Counter

from crownline_human_decision_suite import human_decision_suite


def test_human_decision_suite_is_canonical_and_balanced_by_bucket():
    fixtures = human_decision_suite()
    assert len(fixtures) == 22
    assert len({fixture.fixture_id for fixture in fixtures}) == 22
    assert len({fixture.fingerprint for fixture in fixtures}) == 22
    assert Counter(fixture.bucket for fixture in fixtures) == {
        "human-tactical-error": 7,
        "bot-crownline-construction": 7,
        "human-royal-sweep-preparation": 8,
    }


def test_tactical_fixtures_reproduce_annotated_compound_reply():
    fixtures = [
        fixture
        for fixture in human_decision_suite()
        if fixture.bucket == "human-tactical-error"
    ]
    for fixture in fixtures:
        state = fixture.state()
        move = state.current_game.move_from_notation(fixture.observed_action.notation)
        after = state.apply_move(move, meld_line=fixture.observed_action.meld_line)
        reply = after.current_game.move_from_notation(fixture.annotation["observed_reply"])
        points = sum(
            after.current_game.board[square].capture_value()
            for square in reply.captured
        )
        assert len(reply.captured) == fixture.annotation["observed_reply_capture_legs"]
        assert points == fixture.annotation["observed_reply_capture_points"]


def test_royal_sweep_preparation_targets_all_eight_geometries_once():
    fixtures = [
        fixture
        for fixture in human_decision_suite()
        if fixture.bucket == "human-royal-sweep-preparation"
    ]
    assert [fixture.annotation["sweep_order"] for fixture in fixtures] == list(range(1, 9))
    assert all(fixture.annotation["target_royal"] is True for fixture in fixtures)
    assert len({tuple(fixture.annotation["target_line"]) for fixture in fixtures}) == 8
