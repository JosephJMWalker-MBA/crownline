import crownline_benchmark
from crownline_benchmark import BaselineEngine, _game_state_fingerprint
from crownline_opening_benchmark import _start_benchmark_from, run_opening_suite
from crownline_openings import (
    OPENING_RULES_MODE,
    OPENING_SUITE_ID,
    instantiate_opening,
    opening_suite,
)


def test_opening_suite_is_candidate_only_unique_and_seat_neutral():
    scenarios = opening_suite(OPENING_SUITE_ID)
    assert len(scenarios) == 8
    assert len({scenario.scenario_id for scenario in scenarios}) == len(scenarios)

    fingerprints = []
    for scenario in scenarios:
        state_a, trace_a = instantiate_opening(scenario, first_game_white="A")
        state_b, trace_b = instantiate_opening(scenario, first_game_white="B")

        assert state_a.rules_mode == OPENING_RULES_MODE == "candidate"
        assert state_a.current_game.variant.number == 1
        assert state_a.current_game.ply == scenario.opening_plies
        assert state_b.current_game.ply == scenario.opening_plies
        assert trace_a == trace_b
        assert _game_state_fingerprint(state_a.current_game) == _game_state_fingerprint(
            state_b.current_game
        )
        fingerprints.append(_game_state_fingerprint(state_a.current_game))

    assert len(set(fingerprints)) == len(scenarios)


def test_opening_state_override_restores_standard_constructor():
    scenario = opening_suite()[1]
    state, _ = instantiate_opening(scenario, first_game_white="A")
    original = crownline_benchmark.new_set

    with _start_benchmark_from(state):
        seeded = crownline_benchmark.new_set(
            first_game_white="A",
            rules_mode="candidate",
        )
        assert seeded is state

    assert crownline_benchmark.new_set is original


def test_opening_suite_runner_records_all_scenarios_and_fingerprints():
    report = run_opening_suite(
        BaselineEngine("A-d1", depth=1),
        BaselineEngine("B-d1", depth=1),
        max_game_plies=9,
        repetition_limit=3,
    )

    assert report.schema_version == 1
    assert report.suite_id == OPENING_SUITE_ID
    assert report.rules_mode == "candidate"
    assert report.scenario_count == 8
    assert len(report.scenarios) == 8
    assert all(len(scenario.sets) == 2 for scenario in report.scenarios)
    assert report.summary["distinct_opening_fingerprints"] == 8
    assert len(report.source_fingerprints["opening_suite_sha256"]) == 64
    assert len(report.source_fingerprints["opening_runner_sha256"]) == 64
