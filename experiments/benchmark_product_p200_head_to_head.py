from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from crownline_benchmark import _source_fingerprint
from crownline_position_benchmark import run_position_suite
from crownline_position_suite import POSITION_SUITE_ID, POSITION_SUITE_PATH
from crownline_product_candidate import RepeatAwareStructuralTTOpponent, StructuralTTTimeControl


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


def _meta(engine) -> dict:
    return {
        "budget_ms": engine.budget_ms,
        "max_depth": engine.max_depth,
        "decisions": engine.decisions,
        "mean_completed_depth": engine.mean_completed_depth,
        "timed_out_decisions": engine.timed_out_decisions,
        "repeat_penalty": getattr(engine, "repeat_penalty", None),
        "repeat_candidates_seen": getattr(engine, "repeat_candidates_seen", 0),
        "decisions_with_repeat_candidate": getattr(engine, "decisions_with_repeat_candidate", 0),
        "repeated_action_selected": getattr(engine, "repeated_action_selected", 0),
    }


def run(*, budget_ms: float, max_depth: int, repeat_penalty: float, max_game_plies: int, repetition_limit: int) -> dict:
    control = StructuralTTTimeControl(
        name="stage2-control",
        budget_ms=budget_ms,
        max_depth=max_depth,
    )
    candidate = RepeatAwareStructuralTTOpponent(
        name=f"product-p{repeat_penalty:g}",
        budget_ms=budget_ms,
        max_depth=max_depth,
        repeat_penalty=repeat_penalty,
    )
    report = run_position_suite(
        control,
        candidate,
        suite_id=POSITION_SUITE_ID,
        max_game_plies=max_game_plies,
        repetition_limit=repetition_limit,
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "experiment": "stage2-control-vs-time-budgeted-product-p200",
        "suite_id": POSITION_SUITE_ID,
        "rules_mode": "candidate",
        "budget_ms": budget_ms,
        "max_depth": max_depth,
        "repeat_penalty": repeat_penalty,
        "max_game_plies": max_game_plies,
        "repetition_limit": repetition_limit,
        "engine_a": report.engine_a | _meta(control),
        "engine_b": report.engine_b | _meta(candidate),
        "summary": _compact(report),
        "report": asdict(report),
        "source_fingerprints": {
            "baseline_ai_sha256": _source_fingerprint("crownline_ai.py"),
            "stage2_tt_time_engine_sha256": _source_fingerprint("crownline_tt_time_engine.py"),
            "product_candidate_sha256": _source_fingerprint("crownline_product_candidate.py"),
            "benchmark_harness_sha256": _source_fingerprint("crownline_benchmark.py"),
            "position_runner_sha256": _source_fingerprint("crownline_position_benchmark.py"),
            "position_suite_sha256": _source_fingerprint(str(POSITION_SUITE_PATH.relative_to(ROOT))),
            "experiment_sha256": _source_fingerprint("experiments/benchmark_product_p200_head_to_head.py"),
        },
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Benchmark the 150ms p200 product opponent directly against the Stage-2 time-budgeted control.")
    parser.add_argument("--budget-ms", type=float, default=150.0)
    parser.add_argument("--max-depth", type=int, default=4, choices=range(1, 5))
    parser.add_argument("--repeat-penalty", type=float, default=200.0)
    parser.add_argument("--max-game-plies", type=int, default=300)
    parser.add_argument("--repetition-limit", type=int, default=3)
    parser.add_argument("--json", dest="json_path", default=None)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    report = run(
        budget_ms=args.budget_ms,
        max_depth=args.max_depth,
        repeat_penalty=args.repeat_penalty,
        max_game_plies=args.max_game_plies,
        repetition_limit=args.repetition_limit,
    )
    summary = report["summary"]
    print("Crownline 150ms Stage-2 control vs p200 product candidate")
    print(
        f"complete {summary['complete_sets']}/16 | repetitions {summary['repetition_stops']} | "
        f"pairs {summary['complete_scenario_pairs']}/8 | pair wins {summary['scenario_pair_wins']}"
    )
    print(
        f"paired margins A(control)-B(candidate): {summary['scenario_pair_margins_a_minus_b']} | "
        f"mean {summary['mean_paired_margin_a_minus_b']}"
    )
    print(
        f"aggregate completed score {summary['aggregate_score_totals']} | "
        f"mean depth A/B {report['engine_a']['mean_completed_depth']:.2f}/"
        f"{report['engine_b']['mean_completed_depth']:.2f}"
    )
    print(
        f"candidate repeat selected {report['engine_b']['repeated_action_selected']} | "
        f"cycle lengths {summary['repetition_cycle_lengths']}"
    )
    if args.json_path:
        path = Path(args.json_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"JSON report: {path}")


if __name__ == "__main__":
    main()
