from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from crownline_benchmark import _source_fingerprint
from crownline_history_policy_experiment import RepeatAwareEngine
from crownline_position_benchmark import run_position_suite
from crownline_position_suite import POSITION_SUITE_ID, POSITION_SUITE_PATH


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = 1


def _run_penalty(penalty: float, *, depth: int, max_game_plies: int, repetition_limit: int) -> dict:
    engine_a = RepeatAwareEngine(f"repeat-p{penalty:g}-A", depth, penalty)
    engine_b = RepeatAwareEngine(f"repeat-p{penalty:g}-B", depth, penalty)
    report = run_position_suite(
        engine_a,
        engine_b,
        suite_id=POSITION_SUITE_ID,
        max_game_plies=max_game_plies,
        repetition_limit=repetition_limit,
    )
    summary = report.summary
    return {
        "repeat_penalty": penalty,
        "complete_sets": summary["complete_sets"],
        "repetition_stops": summary["repetition_detected_sets"],
        "complete_scenario_pairs": summary["complete_scenario_pairs"],
        "scenario_pair_wins": summary["scenario_pair_wins"],
        "aggregate_score_totals": summary["aggregate_score_totals"],
        "end_reasons": summary["end_reasons"],
        "repetition_cycle_lengths": summary["repetition_cycle_lengths"],
        "engine_metrics": summary["engine_metrics"],
        "history_metrics": {
            "A_repeat_candidates_seen": engine_a.repeat_candidates_seen,
            "B_repeat_candidates_seen": engine_b.repeat_candidates_seen,
            "A_decisions_with_repeat_candidate": engine_a.decisions_with_repeat_candidate,
            "B_decisions_with_repeat_candidate": engine_b.decisions_with_repeat_candidate,
            "A_repeated_action_selected": engine_a.repeated_action_selected,
            "B_repeated_action_selected": engine_b.repeated_action_selected,
        },
        "report": asdict(report),
    }


def run(penalties: tuple[float, ...], *, depth: int, max_game_plies: int, repetition_limit: int) -> dict:
    results = [
        _run_penalty(
            penalty,
            depth=depth,
            max_game_plies=max_game_plies,
            repetition_limit=repetition_limit,
        )
        for penalty in penalties
    ]
    control = next(result for result in results if result["repeat_penalty"] == 0.0)
    return {
        "schema_version": SCHEMA_VERSION,
        "experiment": "stage3-actual-history-repeat-penalty-sweep",
        "suite_id": POSITION_SUITE_ID,
        "rules_mode": "candidate",
        "depth": depth,
        "penalties": list(penalties),
        "max_game_plies": max_game_plies,
        "repetition_limit": repetition_limit,
        "hypothesis": (
            "Exact repetition is inherently trajectory-dependent. Penalizing only a root action "
            "that recreates an exact CLSN afterstate previously produced by the same participant "
            "in the current game should reduce four-ply shuttle cycles while leaving first-visit "
            "positions and recursive Baseline A evaluation unchanged."
        ),
        "control_repetition_stops": control["repetition_stops"],
        "results": results,
        "source_fingerprints": {
            "baseline_ai_sha256": _source_fingerprint("crownline_ai.py"),
            "history_policy_sha256": _source_fingerprint("crownline_history_policy_experiment.py"),
            "benchmark_harness_sha256": _source_fingerprint("crownline_benchmark.py"),
            "position_runner_sha256": _source_fingerprint("crownline_position_benchmark.py"),
            "position_suite_sha256": _source_fingerprint(str(POSITION_SUITE_PATH.relative_to(ROOT))),
            "experiment_sha256": _source_fingerprint("experiments/benchmark_repeat_penalty_sweep.py"),
        },
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sweep actual-history repeat penalties in Crownline self-play.")
    parser.add_argument("--penalties", type=float, nargs="+", default=(0, 50, 100, 200, 500))
    parser.add_argument("--depth", type=int, default=3, choices=range(1, 5))
    parser.add_argument("--max-game-plies", type=int, default=300)
    parser.add_argument("--repetition-limit", type=int, default=3)
    parser.add_argument("--json", dest="json_path", default=None)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    penalties = tuple(float(p) for p in args.penalties)
    if 0.0 not in penalties:
        raise ValueError("penalties must include 0 as the Baseline A policy control")
    report = run(
        penalties,
        depth=args.depth,
        max_game_plies=args.max_game_plies,
        repetition_limit=args.repetition_limit,
    )
    print("Crownline Stage 3 actual-history repeat-penalty sweep")
    print(f"depth={args.depth} penalties={penalties}")
    for result in report["results"]:
        h = result["history_metrics"]
        print(
            f"p={result['repeat_penalty']:g}: complete {result['complete_sets']}/16 | "
            f"repetitions {result['repetition_stops']} | pairs {result['complete_scenario_pairs']}/8 | "
            f"repeat selected A/B {h['A_repeated_action_selected']}/{h['B_repeated_action_selected']}"
        )
    if args.json_path:
        path = Path(args.json_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"JSON report: {path}")


if __name__ == "__main__":
    main()
