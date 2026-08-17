from __future__ import annotations

import argparse
import json
from contextlib import contextmanager
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Tuple

import crownline_benchmark
from crownline_benchmark import (
    BaselineEngine,
    BenchmarkEngine,
    SetRecord,
    _build_summary,
    _source_fingerprint,
    play_benchmark_set,
)
from crownline_position_suite import (
    POSITION_SUITE_ID,
    POSITION_SUITE_PATH,
    POSITION_SUITE_RULES_MODE,
    PositionScenario,
    position_suite,
)
from crownline_rules import Participant, normalize_rules_mode
from crownline_set import CrownlineSet
from crownline_state_notation import clsn_fingerprint, serialize_clsn


POSITION_REPORT_SCHEMA_VERSION = 1
ROOT = Path(__file__).resolve().parent


@dataclass(frozen=True)
class PositionScenarioRecord:
    scenario_id: str
    description: str
    tags: Tuple[str, ...]
    game1_clsn: str
    game1_fingerprint: str
    game2_clsn: str
    game2_fingerprint: str
    pair_complete: bool
    paired_margin_a_minus_b: int | None
    pair_winner: str | None
    sets: Tuple[SetRecord, SetRecord]


@dataclass(frozen=True)
class PositionSuiteReport:
    schema_version: int
    suite_id: str
    rules_mode: str
    scenario_count: int
    sets_per_scenario: int
    max_game_plies: int
    repetition_limit: int
    deterministic: bool
    engine_a: dict
    engine_b: dict
    source_fingerprints: dict
    summary: dict
    scenarios: Tuple[PositionScenarioRecord, ...]


@contextmanager
def _position_benchmark_context(
    scenario: PositionScenario,
    *,
    first_game_white: Participant,
):
    """Seed both games of a Crownline set from frozen CLSN fixtures.

    The ordinary benchmark loop remains authoritative for moves, metrics,
    repetition diagnostics, Game-1 scoring, participant/color mapping, and final
    set aggregation. This context changes only three boundaries while active:

    * `new_set()` starts from the scenario's canonical Game-1 position;
    * the normal Game-1 -> Game-2 transition substitutes the scenario's canonical
      Game-2 position after the Game-1 result has been recorded;
    * exact-state repetition fingerprints derive from canonical CLSN1.

    Every patched symbol is restored on exit. Runs are intentionally
    single-threaded.
    """

    game1 = scenario.game1.game()
    game2 = scenario.game2.game()
    if game1.variant.number != 1 or game2.variant.number != 2:
        raise ValueError("Position scenario must contain Game 1 and Game 2 fixtures")
    if game1.rules_mode != POSITION_SUITE_RULES_MODE or game2.rules_mode != POSITION_SUITE_RULES_MODE:
        raise ValueError("Position fixtures must use the v1.1 candidate rules")

    original_new_set = crownline_benchmark.new_set
    original_advance_game = CrownlineSet.advance_game
    original_fingerprint = crownline_benchmark._game_state_fingerprint

    def seeded_new_set(
        first_game_white: Participant = "A",
        *,
        rules_mode: str = POSITION_SUITE_RULES_MODE,
    ) -> CrownlineSet:
        normalized = normalize_rules_mode(rules_mode)
        if first_game_white != first_game_white_expected:
            raise ValueError("Position fixture participant mapping does not match benchmark leg")
        if normalized != POSITION_SUITE_RULES_MODE:
            raise ValueError("Position fixture rules do not match benchmark rules")
        base = original_new_set(
            first_game_white=first_game_white,
            rules_mode=normalized,
        )
        return replace(base, current_game=game1)

    def advance_with_frozen_game2(self: CrownlineSet) -> CrownlineSet:
        game_number = self.game_number
        advanced = original_advance_game(self)
        if game_number == 1:
            if advanced.game_number != 2 or len(advanced.completed_games) != 1:
                raise AssertionError("Unexpected Crownline Game-1 transition state")
            return replace(advanced, current_game=game2)
        return advanced

    first_game_white_expected = first_game_white
    crownline_benchmark.new_set = seeded_new_set
    CrownlineSet.advance_game = advance_with_frozen_game2
    crownline_benchmark._game_state_fingerprint = clsn_fingerprint
    try:
        yield
    finally:
        crownline_benchmark.new_set = original_new_set
        CrownlineSet.advance_game = original_advance_game
        crownline_benchmark._game_state_fingerprint = original_fingerprint


def _run_leg(
    engine_a: BenchmarkEngine,
    engine_b: BenchmarkEngine,
    *,
    scenario: PositionScenario,
    first_game_white: Participant,
    pair_index: int,
    leg: str,
    max_game_plies: int,
    repetition_limit: int,
) -> SetRecord:
    with _position_benchmark_context(
        scenario,
        first_game_white=first_game_white,
    ):
        return play_benchmark_set(
            engine_a,
            engine_b,
            first_game_white=first_game_white,
            rules_mode=POSITION_SUITE_RULES_MODE,
            max_game_plies=max_game_plies,
            repetition_limit=repetition_limit,
            pair_index=pair_index,
            leg=leg,
        )


def _scenario_record(
    engine_a: BenchmarkEngine,
    engine_b: BenchmarkEngine,
    *,
    scenario: PositionScenario,
    pair_index: int,
    max_game_plies: int,
    repetition_limit: int,
) -> PositionScenarioRecord:
    a_first = _run_leg(
        engine_a,
        engine_b,
        scenario=scenario,
        first_game_white="A",
        pair_index=pair_index,
        leg="A-first",
        max_game_plies=max_game_plies,
        repetition_limit=repetition_limit,
    )
    b_first = _run_leg(
        engine_a,
        engine_b,
        scenario=scenario,
        first_game_white="B",
        pair_index=pair_index,
        leg="B-first",
        max_game_plies=max_game_plies,
        repetition_limit=repetition_limit,
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

    return PositionScenarioRecord(
        scenario_id=scenario.scenario_id,
        description=scenario.description,
        tags=scenario.tags,
        game1_clsn=scenario.game1.clsn,
        game1_fingerprint=scenario.game1.fingerprint,
        game2_clsn=scenario.game2.clsn,
        game2_fingerprint=scenario.game2.fingerprint,
        pair_complete=pair_complete,
        paired_margin_a_minus_b=paired_margin,
        pair_winner=pair_winner,
        sets=(a_first, b_first),
    )


def _position_summary(records: Tuple[PositionScenarioRecord, ...]) -> dict:
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
        "distinct_game1_fingerprints": len(
            {scenario.game1_fingerprint for scenario in records}
        ),
        "distinct_game2_fingerprints": len(
            {scenario.game2_fingerprint for scenario in records}
        ),
        "distinct_position_fingerprints": len(
            {
                fingerprint
                for scenario in records
                for fingerprint in (
                    scenario.game1_fingerprint,
                    scenario.game2_fingerprint,
                )
            }
        ),
    }


def run_position_suite(
    engine_a: BenchmarkEngine,
    engine_b: BenchmarkEngine,
    *,
    suite_id: str = POSITION_SUITE_ID,
    max_game_plies: int = 300,
    repetition_limit: int = 3,
) -> PositionSuiteReport:
    scenarios = position_suite(suite_id)
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

    return PositionSuiteReport(
        schema_version=POSITION_REPORT_SCHEMA_VERSION,
        suite_id=suite_id,
        rules_mode=POSITION_SUITE_RULES_MODE,
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
            "clsn_sha256": _source_fingerprint("crownline_state_notation.py"),
            "position_suite_sha256": _source_fingerprint(
                str(POSITION_SUITE_PATH.relative_to(ROOT))
            ),
            "position_loader_sha256": _source_fingerprint("crownline_position_suite.py"),
            "position_runner_sha256": _source_fingerprint("crownline_position_benchmark.py"),
        },
        summary=_position_summary(records),
        scenarios=records,
    )


def write_report(report: PositionSuiteReport, destination: str | Path) -> Path:
    path = Path(destination)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(asdict(report), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


def print_summary(report: PositionSuiteReport) -> None:
    summary = report.summary
    wins = summary["scenario_pair_wins"]
    metrics_a = summary["engine_metrics"]["A"]
    metrics_b = summary["engine_metrics"]["B"]
    print("Crownline CLSN position-suite benchmark")
    print(
        f"Suite {report.suite_id} | rules {report.rules_mode} | "
        f"scenarios {report.scenario_count} | frozen positions "
        f"{summary['distinct_position_fingerprints']}"
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
        f"repetition stops: {summary['repetition_detected_sets']}"
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
        description="Run Crownline engines across frozen paired CLSN v1.1 positions."
    )
    parser.add_argument("--suite", default=POSITION_SUITE_ID, choices=(POSITION_SUITE_ID,))
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
    report = run_position_suite(
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
