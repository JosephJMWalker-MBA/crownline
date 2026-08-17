from crownline_king_position_suite import (
    KING_POSITION_SUITE_ID,
    KING_POSITION_SUITE_RULES_MODE,
    king_position_suite,
)
from crownline_state_notation import clsn_fingerprint, serialize_clsn


def test_king_position_suite_is_canonical_unique_and_king_rich():
    fixtures = king_position_suite()

    assert len(fixtures) == 12
    assert len({fixture.fixture_id for fixture in fixtures}) == 12
    assert len({fixture.fingerprint for fixture in fixtures}) == 12

    for fixture in fixtures:
        game = fixture.game()
        assert game.rules_mode == KING_POSITION_SUITE_RULES_MODE
        assert not game.game_over
        assert serialize_clsn(game) == fixture.clsn
        assert clsn_fingerprint(game) == fixture.fingerprint
        assert any(piece.king for piece in game.board.values())
        assert fixture.source.workflow_run > 0
        assert fixture.source.artifact_id > 0


def test_king_position_suite_covers_both_geometries_and_cycle_shapes():
    fixtures = king_position_suite()

    assert {fixture.game().variant.number for fixture in fixtures} == {1, 2}
    assert {4, 8, 20}.issubset({fixture.cycle_length for fixture in fixtures})
    assert any(fixture.cycle_length == 20 for fixture in fixtures)
    assert any(fixture.game().variant.number == 2 for fixture in fixtures)


def test_king_position_suite_contains_varied_king_counts_and_meld_contexts():
    fixtures = king_position_suite()
    king_counts = {fixture.king_count for fixture in fixtures}

    assert min(king_counts) >= 2
    assert max(king_counts) >= 6
    assert len(king_counts) >= 4
    assert any(fixture.game().melds_w or fixture.game().melds_b for fixture in fixtures)
    assert any(
        meld.royal
        for fixture in fixtures
        for meld in fixture.game().melds_w + fixture.game().melds_b
    )


def test_unknown_king_position_suite_is_rejected():
    try:
        king_position_suite("not-a-suite")
    except ValueError as exc:
        assert "Unknown King position suite" in str(exc)
    else:
        raise AssertionError("unknown King position suite should fail")


def test_king_position_suite_identity_is_stable():
    assert KING_POSITION_SUITE_ID == "king-v0.1"
