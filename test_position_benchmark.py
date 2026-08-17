from dataclasses import replace

import crownline_benchmark
from crownline_benchmark import BaselineEngine
from crownline_position_benchmark import (
    POSITION_REPORT_SCHEMA_VERSION,
    _position_benchmark_context,
    run_position_suite,
)
from crownline_position_suite import position_suite
from crownline_state_notation import clsn_fingerprint, serialize_clsn


def test_position_context_injects_both_frozen_games_and_restores_hooks():
    scenario = next(
        item for item in position_suite() if item.scenario_id == "standard-start"
    )
    original_new_set = crownline_benchmark.new_set
    original_advance = crownline_benchmark.CrownlineSet.advance_game
    original_fingerprint = crownline_benchmark._game_state_fingerprint

    with _position_benchmark_context(scenario, first_game_white="A"):
        state = crownline_benchmark.new_set(
            first_game_white="A",
            rules_mode="candidate",
        )
        assert serialize_clsn(state.current_game) == scenario.game1.clsn
        assert crownline_benchmark._game_state_fingerprint(state.current_game) == scenario.game1.fingerprint
        assert crownline_benchmark._game_state_fingerprint(state.current_game) == clsn_fingerprint(state.current_game)

        terminal_game1 = replace(
            state.current_game,
            game_over=True,
            end_reason="immobilization",
        )
        state = replace(state, current_game=terminal_game1)
        advanced = state.advance_game()

        assert len(advanced.completed_games) == 1
        assert advanced.game_number == 2
        assert serialize_clsn(advanced.current_game) == scenario.game2.clsn
        assert crownline_benchmark._game_state_fingerprint(advanced.current_game) == scenario.game2.fingerprint

    assert crownline_benchmark.new_set is original_new_set
    assert crownline_benchmark.CrownlineSet.advance_game is original_advance
    assert crownline_benchmark._game_state_fingerprint is original_fingerprint


def test_position_context_preserves_participant_color_mapping_across_game2():
    scenario = next(
        item for item in position_suite() if item.scenario_id == "standard-start"
    )

    with _position_benchmark_context(scenario, first_game_white="B"):
        state = crownline_benchmark.new_set(
            first_game_white="B",
            rules_mode="candidate",
        )
        assert state.white_participant == "B"
        assert state.black_participant == "A"

        state = replace(
            state,
            current_game=replace(
                state.current_game,
                game_over=True,
                end_reason="immobilization",
            ),
        ).advance_game()

        assert state.white_participant == "A"
        assert state.black_participant == "B"
        assert serialize_clsn(state.current_game) == scenario.game2.clsn


def test_short_position_suite_run_reports_frozen_fixture_identity():
    engine_a = BaselineEngine("A-d1", depth=1)
    engine_b = BaselineEngine("B-d1", depth=1)

    report = run_position_suite(
        engine_a,
        engine_b,
        max_game_plies=1,
        repetition_limit=3,
    )

    assert report.schema_version == POSITION_REPORT_SCHEMA_VERSION
    assert report.rules_mode == "candidate"
    assert report.scenario_count == 8
    assert report.sets_per_scenario == 2
    assert len(report.scenarios) == 8
    assert report.summary["complete_scenario_pairs"] == 0
    assert report.summary["incomplete_scenario_pairs"] == 8
    assert report.summary["complete_sets"] == 0
    assert report.summary["capped_sets"] == 16
    assert report.summary["distinct_game1_fingerprints"] == 8
    assert report.summary["distinct_game2_fingerprints"] == 8
    assert report.summary["distinct_position_fingerprints"] == 16
    assert all(len(scenario.sets) == 2 for scenario in report.scenarios)
    assert all(
        scenario.sets[0].first_game_white == "A"
        and scenario.sets[1].first_game_white == "B"
        for scenario in report.scenarios
    )
    assert len(report.source_fingerprints["clsn_sha256"]) == 64
    assert len(report.source_fingerprints["position_suite_sha256"]) == 64
    assert len(report.source_fingerprints["position_runner_sha256"]) == 64
