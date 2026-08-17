from __future__ import annotations

import argparse
import json
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Tuple

import crownline_benchmark
from crownline_benchmark import (
    BaselineEngine,
    BenchmarkEngine,
    SetRecord,
    _build_summary,
    _game_state_fingerprint,
    _source_fingerprint,
    play_benchmark_set,
)
from crownline_openings import (
    OPENING_RULES_MODE,
    OPENING_SELECTION_METHOD,
    OPENING_SUITE_ID,
    OpeningScenario,
    OpeningStep,
    instantiate_opening,
    opening_suite,
)
from crownline_rules import Participant, normalize_rules_mode
from crownline_set import CrownlineSet


SUITE_REPORT_SCHEMA_VERSION = 1
ROOT = Path(__file__).resolve().parent


@dataclass(frozen=True)
class ScenarioRecord:
    scenario_id: str
    description: str
    tags: Tuple[str, ...]
    opening_plies: int
    opening_fingerprint: str
    opening_trace: Tuple[OpeningStep, ...]
    pair_complete: bool
    paired_margin_a_minus_b: int | None
    pair_winner: str | None
    sets: Tuple[SetRecord, SetRecord]


@dataclass(frozen=True)
class OpeningSuiteReport:
    schema_version: int
    suite_id: str
    rules_mode: str
    selection_method: str
    scenario_count: int
    sets_per_scenario: int
    max_game_plies: int
    repetition_limit: int
    deterministic: bool
    engine_a: dict
    engine_b: dict
    source_fingerprints: dict
    summary: dict
    scenarios: Tuple[ScenarioRecord, ...]


@contextmanager
def _start_benchmark_from(state: CrownlineSet):
    """Inject a validated opening state into the existing benchmark loop.

    `play_benchmark_set` intentionally owns the game loop. This narrow harness
    override changes only the state returned by its initial `new_set` call, then
    restores the original constructor immediately. It preserves all existing
    metrics, repetition diagnostics, set advancement, and engine behavior.
    Opening-suite runs are intentionally single-threaded.
    """

    original = crownline_benchmark.new_set

    def seeded_new_set(
        first_game_white: Participant = "A",
        *,
        rules_mode: str = OPENING_RULES_MODE,
    ) -> CrownlineSet:
        normalized = normalize_rules_mode(rules_mode)
        if first_game_white != state.first_game_white:
            raise ValueError("opening state participant mapping does not match benchmark leg")
        if normalized != state.rules_mode:
            raise ValueError("opening state rules do not match benchmark rules")
        return state

    crownline_benchmark.new_set = seeded_new_set
    try:
        yield
    finally:
        crownline_benchmark.new_set = original


def _run_leg(
    engine_a: BenchmarkEngine,
    engine_b: BenchmarkEngine,
    *,
    scenario: OpeningScenario,
    first_game_white: Participant,
    pair_index: int,
    leg: str,
    max_game_plies: int,
    repetition_limit: int,
) -> tuple[SetRecord, str, Tuple[OpeningStep, ...]]:
    state, trace = instantiate_opening(
        scenario,
        first_game_white=first_game_white,
    )
    fingerprint = _game_state_fingerprint(state.current_game)
    with _start_benchmark_from(state):
        record = play_benchmark_set(
            engine_a,
            engine_b,
            first_game_white=first_game_white,
            rules_mode=scenario.rules_mode,
            max_game_plies=max_game_plies,
            repetition_limit=repetition_limit,
            pair_index=pair_index,
            leg=leg,
        )
    return record, fingerprint, trace


def _scenario_record(
    engine_a: BenchmarkEngine,
    engine_b: BenchmarkEngine,
    *,
    scenario: OpeningScenario,
    pair_index: int,
    max_game_plies: int,
    repetition_limit: int,
) -> ScenarioRecord:
    a_first, fp_a, trace_a = _run_leg(
        engine_a,
        engine_b,
        scenario=scenario,
        first_game_white="A",
        pair_index=pair_index,
        leg="A-first",
        max_game_plies=max_game_plies,
        repetition_limit=repetition_limit,
    )
    b_first, fp_b, trace_b = _run_leg(
        engine_a,
        engine_b,
        scenario=scenario,
        first_game_white="B",
        pair_index=pair_index,
        leg="B-first",
        max_game_plies=max_game_plies,
        repetition_limit=repetition_limit,
    )

    # Participant identity must not change the color-level opening position.
    if fp_a != fp_b or trace_a != trace_b:
        raise AssertionError(
            f"Opening scenario {scenario.scenario_id} is not seat-neutral"
        )

    pair_complete = a_first.complete and b_first.complete
    paired_margin = None
    pair_winner = None
    if pair_complete:
        paired_margin = (
            a_first.aggregate_a
            - a_first.aggregate_b
            + b_first.aggregate_a
            - b_first.aggregate_b
        )
        pair_winner = "A" if paired_margin > 0 else "B" if paired_margin < 0 else "DRAW"

    return ScenarioRecord(
        scenario_id=scenario.scenario_id,
        description=scenario.description,
        tags=scenario.tags,
        opening_plies=scenario.opening_plies,
        opening_fingerprint=fp_a,
        opening_trace=trace_a,
        pair_complete=pair_complete,
        paired_margin_a_minus_b=paired_margin,
        pair_winner=pair_winner,
        sets=(a_first, b_first),
    )


def _suite_summary(records: Tuple[ScenarioRecord, ...]) -> dict:
    sets = tuple(set_record for scenario in records for set_record in scenario.sets)
    base = _build_summary(sets)
    complete_scenarios = [scenario for scenario in records if scenario.pair_complete]
    wins_a = sum(scenario.pair_winner == "A" for scenario in complete_scenarios)
    wins_b = sum(scenario.pair_winner == "B" for scenario in complete_scenarios)
    draws = sum(scenario.pair_winner == "DRAW" for scenario in complete_scenarios)

    return {
        **base,
        "scenario_count": len(records),
        "complete_scenario_pairs": len(complete_scenarios),
        "incomplete_scenario_pairs": len(records) - len(complete_scenarios),
        "scenario_pair_wins": {"A": wins_a, "B": wins_b, "draws": draws},
        "scenario_pair_margins_a_minus_b": [
            scenario.paired_margin_a_minus_b for scenario in complete_scenarios
        ],
        "distinct_opening_fingerprints": len(
            {scenario.opening_fingerprint for scenario in records}
        ),
    }


def run_opening_suite(
    engine_a: BenchmarkEngine,
    engine_b: BenchmarkEngine,
    *,
    suite_id: str = OPENING_SUITE_ID,
    max_game_plies: int = 300,
    repetition_limit: int = 3,
) -> OpeningSuiteReport:
    scenarios = opening_suite(suite_id)
    records = tuple(
        _scenario_record(
            engine_a,
            engine_b,
            scenario=scenario,
            pair_index=index,
            max_game_plies=max_game_plies,
            repetition_limit=repetition_limit,
        )
        for index, scenario in enumerate(scenarios, start=1)
    )

    fingerprints = {scenario.opening_fingerprint for scenario in records}
    if len(fingerprints) != len(records):
        raise AssertionError("Opening suite contains duplicate canonical starting states")

    return OpeningSuiteReport(
        schema_version=SUITE_REPORT_SCHEMA_VERSION,
        suite_id=suite_id,
        rules_mode=OPENING_RULES_MODE,
        selection_method=OPENING_SELECTION_METHOD,
        scenario_count=len(records),
        sets_per_scenario=2,
        max_game_plies=max_game_plies,
        repetition_limit=repetition_limit,
        deterministic=True,
        engine_a={
            "participant": "A",
            "name": engine_a.name,
            "type": type(engine_a).__name__,
            "depth": getattr(engine_a, "depth", None),
        },
        engine_b={
            "participant": "B",
            "name": engine_b.name,
            "type": type(engine_b).__name__,
            "depth": getattr(engine_b, "depth", None),
        },
        source_fingerprints={
            "baseline_ai_sha256": _source_fingerprint("crownline_ai.py"),
            "rules_engine_sha256": _source_fingerprint(
                "crownline_rules.py",
                "crownline_game.py",
                "crownline_set.py",
            ),
            "benchmark_harness_sha256": _source_fingerprint("crownline_benchmark.py"),
            "opening_suite_sha256": _source_fingerprint("crownline_openings.py"),
            "opening_runner_sha256": _source_fingerprint("crownline_opening_benchmark.py"),
        },
        summary=_suite_summary(records),
        scenarios=records,
    )


def write_report(report: OpeningSuiteReport, destination: str | Path) -> Path:
    path = Path(destination)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(asdict(report), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


def print_summary(report: OpeningSuiteReport) -> None:
    summary = report.summary
    wins = summary["scenario_pair_wins"]
    metrics_a = summary["engine_metrics"]["A"]
    metrics_b = summary["engine_metrics"]["B"]
    print("Crownline opening-suite benchmark")
    print(
        f"Suite {report.suite_id} | rules {report.rules_mode} | "
        f"scenarios {report.scenario_count} | sets {report.scenario_count * 2}"
    )
    print(
        f"A: {report.engine_a['name']} (depth {report.engine_a['depth']}) | "
        f"B: {report.engine_b['name']} (depth {report.engine_b['depth']})"
    )
    print(
        f"Complete scenario pairs: {summary['complete_scenario_pairs']} | "
        f"incomplete: {summary['incomplete_scenario_pairs']} | "
        f"A wins {wins['A']} | B wins {wins['B']} | draws {wins['draws']}"
    )
    print(
        f"Complete sets: {summary['complete_sets']} | "
        f"repetition stops: {summary['repetition_detected_sets']} | "
        f"distinct openings: {summary['distinct_opening_fingerprints']}"
    )
    print(
        f"A search: {metrics_a['mean_decision_ms']:.2f} ms/decision | "
        f"{metrics_a['mean_search_nodes']:.1f} nodes/decision"
    )
    print(
        f"B search: {metrics_b['mean_decision_ms']:.2f} ms/decision | "
        f"{metrics_b['mean_search_nodes']:.1f} nodes/decision"
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run Crownline engines across the frozen v1.1 opening suite."
    )
    parser.add_argument("--suite", default=OPENING_SUITE_ID, choices=(OPENING_SUITE_ID,))
    parser.add_argument("--depth-a", type=int, default=2, choices=range(1, 5))
    parser.add_argument("--depth-b", type=int, default=3, choices=range(1, 5))
    parser.add_argument("--name-a", default=None)
    parser.add_argument("--name-b", default=None)
    parser.add_argument("--max-game-plies", type=int, default=300)
    parser.add_argument(
        "--repetition-limit",
        type=int,
        default=3,
        help="diagnostic exact-state occurrence limit; 0 disables",
    )
    parser.add_argument("--json", dest="json_path", default=None)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    engine_a = BaselineEngine(args.name_a or f"baseline-d{args.depth_a}", args.depth_a)
    engine_b = BaselineEngine(args.name_b or f"baseline-d{args.depth_b}", args.depth_b)
    report = run_opening_suite(
        engine_a,
        engine_b,
        suite_id=args.suite,
        max_game_plies=args.max_game_plies,
        repetition_limit=args.repetition_limit,
    )
    print_summary(report)
    if args.json_path:
        path = write_report(report, args.json_path)
        print(f"JSON report: {path}")


if __name__ == "__main__":
    main()
