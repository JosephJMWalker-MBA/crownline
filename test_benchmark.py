from dataclasses import replace

import crownline as c
import crownline_ai
from crownline_benchmark import (
    BaselineEngine,
    RepetitionTracker,
    _game_state_fingerprint,
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


def test_game_state_fingerprint_ignores_ply_but_captures_future_relevant_state():
    game = c.GameState(
        board={
            C("a1"): c.Piece("W", 1, king=True),
            C("h8"): c.Piece("B", 2, king=True),
        },
        variant=c.GAME1,
        rules_mode="candidate",
        turn="W",
    )

    assert _game_state_fingerprint(game) == _game_state_fingerprint(replace(game, ply=99))
    assert _game_state_fingerprint(game) != _game_state_fingerprint(replace(game, turn="B"))
    assert _game_state_fingerprint(game) != _game_state_fingerprint(
        replace(game, cooldowns_w=((1, 2),))
    )


def test_repetition_tracker_reports_exact_cycle_and_escape_options():
    game = c.GameState(
        board={
            C("a1"): c.Piece("W", 1, king=True),
            C("h8"): c.Piece("B", 2, king=True),
        },
        variant=c.GAME1,
        rules_mode="candidate",
        turn="W",
    )
    state = replace(
        c.new_set(first_game_white="A", rules_mode="candidate"),
        current_game=game,
    )
    tracker = RepetitionTracker.start(state, limit=3)

    cycle = ("a1-b2", "h8-g7", "b2-a1", "g7-h8")
    diagnostic = None
    for notation in cycle * 2:
        before = state
        move = before.current_game.move_from_notation(notation)
        participant = before.participant_for_color(before.current_game.turn)
        state = before.apply_move(move)
        diagnostic = tracker.observe(
            before,
            state,
            participant=participant,
            move=move,
            meld_line=None,
            sovereign_opportunity=False,
        )

    assert diagnostic is not None
    assert diagnostic.occurrence_count == 3
    assert diagnostic.first_seen_ply == 0
    assert diagnostic.first_repeat_ply == 4
    assert diagnostic.previous_seen_ply == 4
    assert diagnostic.detected_ply == 8
    assert diagnostic.cycle_length == 4
    assert tuple(trace.notation for trace in diagnostic.cycle_moves) == cycle
    assert diagnostic.first_repeat_observed.first_seen_ply == 0
    assert diagnostic.first_repeat_observed.repeated_ply == 4
    assert diagnostic.repeated_state["turn"] == "W"
    assert diagnostic.sovereign_in_cycle is False
    # The repeated a1/h8 state is forced, but intermediate King positions have
    # legal deviations; the diagnostic inspects every decision state in-cycle.
    assert diagnostic.positions_with_escape_actions > 0
    assert diagnostic.escape_actions > 0
    assert diagnostic.escape_action_examples


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

    assert report.schema_version == 2
    assert report.pairs == 1
    assert report.sets_per_pair == 2
    assert report.repetition_limit == 3
    assert [record.first_game_white for record in report.sets] == ["A", "B"]
    assert [record.leg for record in report.sets] == ["A-first", "B-first"]
    assert all(not record.complete for record in report.sets)
    assert all(record.capped_game == 1 for record in report.sets)
    assert report.summary["complete_sets"] == 0
    assert report.summary["capped_sets"] == 2
    assert report.summary["repetition_detected_sets"] == 0
    assert len(report.source_fingerprints["baseline_ai_sha256"]) == 64
    assert len(report.source_fingerprints["rules_engine_sha256"]) == 64
    assert len(report.source_fingerprints["benchmark_harness_sha256"]) == 64
