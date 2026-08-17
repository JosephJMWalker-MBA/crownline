from dataclasses import replace

import crownline as c
import crownline_ai
from crownline_benchmark import (
    BaselineEngine,
    _sovereign_opportunity,
    run_benchmark,
)


def C(square):
    return c.alg_to_coord(square)


def test_baseline_engine_counts_search_nodes_without_replacing_bot_permanently():
    state = c.new_set(first_game_white="A", rules_mode="candidate")
    engine = BaselineEngine("baseline-d1", depth=1)
    original_search = crownline_ai._search

    decision = engine.choose(state, "A")

    assert crownline_ai._search is original_search
    assert decision.notation in {move.notation() for move in state.current_game.legal_moves()}
    assert decision.root_actions > 0
    # At depth 1, each root action makes exactly one depth-0 _search call.
    assert decision.search_nodes == decision.root_actions
    assert decision.elapsed_ms >= 0


def test_sovereign_opportunity_requires_king_capture_plus_noncapture_choice():
    game = c.GameState(
        board={
            C("c3"): c.Piece("W", 2, king=True),
            C("d4"): c.Piece("B", 4),
            C("g1"): c.Piece("W", 1),
        },
        rules_mode="candidate",
        turn="W",
    )

    legal = {move.notation() for move in game.legal_moves()}
    assert "c3xe5" in legal
    assert any("-" in notation for notation in legal)
    assert _sovereign_opportunity(game)

    official = replace(game, rules_mode="official")
    assert [move.notation() for move in official.legal_moves()] == ["c3xe5"]
    assert not _sovereign_opportunity(official)


def test_benchmark_pair_alternates_game1_starting_color_and_marks_caps():
    engine_a = BaselineEngine("A-d1", depth=1)
    engine_b = BaselineEngine("B-d1", depth=1)

    report = run_benchmark(
        engine_a,
        engine_b,
        pairs=1,
        rules_mode="candidate",
        max_game_plies=1,
    )

    assert report.schema_version == 1
    assert report.pairs == 1
    assert report.sets_per_pair == 2
    assert [record.first_game_white for record in report.sets] == ["A", "B"]
    assert [record.leg for record in report.sets] == ["A-first", "B-first"]
    assert all(not record.complete for record in report.sets)
    assert all(record.capped_game == 1 for record in report.sets)
    assert report.summary["complete_sets"] == 0
    assert report.summary["capped_sets"] == 2
    assert len(report.source_fingerprints["baseline_ai_sha256"]) == 64
    assert len(report.source_fingerprints["rules_engine_sha256"]) == 64
    assert len(report.source_fingerprints["benchmark_harness_sha256"]) == 64
