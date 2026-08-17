from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from crownline_benchmark import _source_fingerprint
from crownline_position_benchmark import run_position_suite
from crownline_position_suite import POSITION_SUITE_ID, POSITION_SUITE_PATH
from crownline_product_candidate import (
    RepeatAwareStructuralTTOpponent,
    StructuralTTTimeControl,
)


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


def _engine_meta(engine) -> dict:
    return {
        "budget_ms": getattr(engine, "budget_ms", None),
        "max_depth": getattr(engine, "max_depth", None),
        "decisions": getattr(engine, "decisions", 0),
        "mean_completed_depth": getattr(engine, "mean_completed_depth", 0.0),
        "timed_out_decisions": getattr(engine, "timed_out_decisions", 0),
        "repeat_penalty": getattr(engine, "repeat_penalty", None),
        "repeat_candidates_seen": getattr(engine, "repeat_candidates_seen", 0),
        "decisions_with_repeat_candidate": getattr(engine, "decisions_with_repeat_candidate", 0),
        "repeated_action_selected": getattr(engine, "repeated_action_selected", 0),
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
        "engine_a": report.engine_a | _engine_meta(engine_a),
        "engine_b": report.engine_b | _engine_meta(engine_b),
        "summary": _compact(report),
        "report": asdict(report),
    }


def _control(name: str, budget_ms: float, max_depth: int):
    return StructuralTTTimeControl(
        name=name,
        budget_ms=budget_ms,
        max_depth=max_depth,
    )


def _candidate(name: str, budget_ms: float, max_depth: int, repeat_penalty: float):
    return RepeatAwareStructuralTTOpponent(
        name=name,
        budget_ms=budget_ms,
        max_depth=max_depth,
        repeat_penalty=repeat_penalty,
    )


def run(*, budget_ms: float, max_depth: int, repeat_penalty: float, max_game_plies: int, repetition_limit: int) -> dict:
    control_self = _run_matchup(
        "stage2-control-self",
        _control("stage2-control-A", budget_ms, max_depth),
        _control("stage2-control-B", budget_ms, max_depth),
        max_game_plies=max_game_plies,
        repetition_limit=repetition_limit,
    )
    candidate_self = _run_matchup(
        "product-candidate-self",
        _candidate("product-candidate-A", budget_ms, max_depth, repeat_penalty),
        _candidate("product-candidate-B", budget_ms, max_depth, repeat_penalty),
        max_game_plies=max_game_plies,
        repetition_limit=repetition_limit,
    )
    head_to_head = _run_matchup(
        "stage2-control-vs-product-candidate",
        _control("stage2-control", budget_ms, max_depth),
        _candidate("product-candidate", budget_ms, max_depth, repeat_penalty),
        max_game_plies=max_game_plies,
        repetition_limit=repetition_limit,
    )

    c = control_self["summary"]
    p = candidate_self["summary"]
    return {
        "schema_version": SCHEMA_VERSION,
        "experiment": "stage2-structural-tt-plus-stage3-repeat-policy-product-candidate",
        "suite_id": POSITION_SUITE_ID,
        "rules_mode": "candidate",
        "budget_ms": budget_ms,
        "max_depth": max_depth,
        "repeat_penalty": repeat_penalty,
        "max_game_plies": max_game_plies,
        "repetition_limit": repetition_limit,
        "hypothesis": (
            "The Stage-2 iterative structural exact-TT search substrate and the independently "
            "measured Stage-3 50-point exact-history repeat policy should compose into a "
            "responsive opponent that reduces trajectory repetition without sacrificing paired "
            "outcomes relative to the same time-budgeted search substrate."
        ),
        "primary_comparison": {
            "control_complete_sets": c["complete_sets"],
            "candidate_complete_sets": p["complete_sets"],
            "complete_set_change": p["complete_sets"] - c["complete_sets"],
            "control_repetition_stops": c["repetition_stops"],
            "candidate_repetition_stops": p["repetition_stops"],
            "repetition_stop_change": p["repetition_stops"] - c["repetition_stops"],
            "control_complete_pairs": c["complete_scenario_pairs"],
            "candidate_complete_pairs": p["complete_scenario_pairs"],
            "control_mean_depth_a": control_self["engine_a"]["mean_completed_depth"],
            "control_mean_depth_b": control_self["engine_b"]["mean_completed_depth"],
            "candidate_mean_depth_a": candidate_self["engine_a"]["mean_completed_depth"],
            "candidate_mean_depth_b": candidate_self["engine_b"]["mean_completed_depth"],
        },
        "matchups": [control_self, candidate_self, head_to_head],
        "source_fingerprints": {
            "baseline_ai_sha256": _source_fingerprint("crownline_ai.py"),
            "stage2_tt_time_engine_sha256": _source_fingerprint("crownline_tt_time_engine.py"),
            "product_candidate_sha256": _source_fingerprint("crownline_product_candidate.py"),
            "benchmark_harness_sha256": _source_fingerprint("crownline_benchmark.py"),
            "position_runner_sha256": _source_fingerprint("crownline_position_benchmark.py"),
            "position_suite_sha256": _source_fingerprint(str(POSITION_SUITE_PATH.relative_to(ROOT))),
            "experiment_sha256": _source_fingerprint("experiments/benchmark_product_candidate_150ms.py"),
        },
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Benchmark the Stage-2 structural-TT + Stage-3 repeat-policy opponent candidate."
    )
    parser.add_argument("--budget-ms", type=float, default=150.0)
    parser.add_argument("--max-depth", type=int, default=4, choices=range(1, 5))
    parser.add_argument("--repeat-penalty", type=float, default=50.0)
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
    print("Crownline product-opponent candidate benchmark")
    print(
        f"budget={report['budget_ms']} ms max_depth={report['max_depth']} "
        f"repeat_penalty={report['repeat_penalty']}"
    )
    for matchup in report["matchups"]:
        s = matchup["summary"]
        print(
            f"{matchup['name']}: complete {s['complete_sets']}/16 | "
            f"repetitions {s['repetition_stops']} | pairs {s['complete_scenario_pairs']}/8 | "
            f"pair wins {s['scenario_pair_wins']} | mean depth A/B "
            f"{matchup['engine_a']['mean_completed_depth']:.2f}/"
            f"{matchup['engine_b']['mean_completed_depth']:.2f}"
        )
    p = report["primary_comparison"]
    print(
        "self-play: complete "
        f"{p['control_complete_sets']} -> {p['candidate_complete_sets']} | "
        f"repetition {p['control_repetition_stops']} -> {p['candidate_repetition_stops']}"
    )
    if args.json_path:
        path = Path(args.json_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"JSON report: {path}")


if __name__ == "__main__":
    main()
