from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from crownline_benchmark import BaselineEngine, _source_fingerprint
from crownline_line_pressure_experiment import LinePressureEngine
from crownline_position_benchmark import run_position_suite
from crownline_position_suite import POSITION_SUITE_ID, POSITION_SUITE_PATH


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = 1


def _compact(report) -> dict:
    summary = report.summary
    return {
        "complete_scenario_pairs": summary["complete_scenario_pairs"],
        "incomplete_scenario_pairs": summary["incomplete_scenario_pairs"],
        "complete_sets": summary["complete_sets"],
        "repetition_stops": summary["repetition_detected_sets"],
        "scenario_pair_wins": summary["scenario_pair_wins"],
        "scenario_pair_margins_a_minus_b": summary["scenario_pair_margins_a_minus_b"],
        "set_wins": summary["set_wins"],
        "aggregate_score_totals": summary["aggregate_score_totals"],
        "mean_set_margin_a_minus_b": summary["mean_set_margin_a_minus_b"],
        "mean_paired_margin_a_minus_b": summary["mean_paired_margin_a_minus_b"],
        "end_reasons": summary["end_reasons"],
        "engine_metrics": summary["engine_metrics"],
        "repetition_cycle_lengths": summary["repetition_cycle_lengths"],
        "repetition_escape_actions": summary["repetition_escape_actions"],
    }


def _run_matchup(name: str, engine_a, engine_b, *, max_game_plies: int, repetition_limit: int) -> dict:
    report = run_position_suite(
        engine_a,
        engine_b,
        suite_id=POSITION_SUITE_ID,
        max_game_plies=max_game_plies,
        repetition_limit=repetition_limit,
    )
    return {
        "name": name,
        "engine_a": report.engine_a | {
            "pressure_weight": getattr(engine_a, "pressure_weight", 0.0),
        },
        "engine_b": report.engine_b | {
            "pressure_weight": getattr(engine_b, "pressure_weight", 0.0),
        },
        "summary": _compact(report),
        "report": asdict(report),
    }


def run(*, depth: int, pressure_weight: float, max_game_plies: int, repetition_limit: int) -> dict:
    baseline_self = _run_matchup(
        "baseline-self",
        BaselineEngine(f"baseline-d{depth}-A", depth),
        BaselineEngine(f"baseline-d{depth}-B", depth),
        max_game_plies=max_game_plies,
        repetition_limit=repetition_limit,
    )
    pressure_self = _run_matchup(
        "line-pressure-self",
        LinePressureEngine(f"pressure-w{pressure_weight:g}-d{depth}-A", depth, pressure_weight),
        LinePressureEngine(f"pressure-w{pressure_weight:g}-d{depth}-B", depth, pressure_weight),
        max_game_plies=max_game_plies,
        repetition_limit=repetition_limit,
    )
    head_to_head = _run_matchup(
        "baseline-vs-line-pressure",
        BaselineEngine(f"baseline-d{depth}", depth),
        LinePressureEngine(f"pressure-w{pressure_weight:g}-d{depth}", depth, pressure_weight),
        max_game_plies=max_game_plies,
        repetition_limit=repetition_limit,
    )

    baseline_rep = baseline_self["summary"]["repetition_stops"]
    pressure_rep = pressure_self["summary"]["repetition_stops"]
    baseline_complete = baseline_self["summary"]["complete_sets"]
    pressure_complete = pressure_self["summary"]["complete_sets"]

    return {
        "schema_version": SCHEMA_VERSION,
        "experiment": "stage3-crownline-pressure-full-trajectory",
        "suite_id": POSITION_SUITE_ID,
        "rules_mode": "candidate",
        "depth": depth,
        "pressure_weight": pressure_weight,
        "max_game_plies": max_game_plies,
        "repetition_limit": repetition_limit,
        "hypothesis": (
            "The Stage 3.2 open/unretired Crownline construction-and-denial pressure term "
            "reduces exact reversible King-shuttle repetition over complete frozen-suite "
            "trajectories without any explicit repetition rule or history-aware penalty."
        ),
        "primary_comparison": {
            "baseline_self_repetition_stops": baseline_rep,
            "pressure_self_repetition_stops": pressure_rep,
            "repetition_stop_change": pressure_rep - baseline_rep,
            "baseline_self_complete_sets": baseline_complete,
            "pressure_self_complete_sets": pressure_complete,
            "complete_set_change": pressure_complete - baseline_complete,
        },
        "matchups": [baseline_self, pressure_self, head_to_head],
        "source_fingerprints": {
            "baseline_ai_sha256": _source_fingerprint("crownline_ai.py"),
            "pressure_engine_sha256": _source_fingerprint("crownline_line_pressure_experiment.py"),
            "benchmark_harness_sha256": _source_fingerprint("crownline_benchmark.py"),
            "position_runner_sha256": _source_fingerprint("crownline_position_benchmark.py"),
            "position_suite_sha256": _source_fingerprint(str(POSITION_SUITE_PATH.relative_to(ROOT))),
            "experiment_sha256": _source_fingerprint("experiments/benchmark_line_pressure_trajectory.py"),
        },
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Crownline-pressure evaluator over complete frozen-suite trajectories.")
    parser.add_argument("--depth", type=int, default=3, choices=range(1, 5))
    parser.add_argument("--pressure-weight", type=float, default=200.0)
    parser.add_argument("--max-game-plies", type=int, default=300)
    parser.add_argument("--repetition-limit", type=int, default=3)
    parser.add_argument("--json", dest="json_path", default=None)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    report = run(
        depth=args.depth,
        pressure_weight=args.pressure_weight,
        max_game_plies=args.max_game_plies,
        repetition_limit=args.repetition_limit,
    )
    print("Crownline Stage 3 Crownline-pressure full-trajectory benchmark")
    print(f"depth={report['depth']} pressure_weight={report['pressure_weight']}")
    for matchup in report["matchups"]:
        s = matchup["summary"]
        print(
            f"{matchup['name']}: complete sets {s['complete_sets']}/16 | "
            f"repetition stops {s['repetition_stops']} | "
            f"scenario pairs {s['complete_scenario_pairs']}/8 | "
            f"pair wins {s['scenario_pair_wins']}"
        )
    p = report["primary_comparison"]
    print(
        "self-play repetition change: "
        f"{p['baseline_self_repetition_stops']} -> {p['pressure_self_repetition_stops']} "
        f"({p['repetition_stop_change']:+d})"
    )
    if args.json_path:
        path = Path(args.json_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"JSON report: {path}")


if __name__ == "__main__":
    main()
