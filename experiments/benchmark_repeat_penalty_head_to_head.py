from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from crownline_benchmark import BaselineEngine, _source_fingerprint
from crownline_history_policy_experiment import RepeatAwareEngine
from crownline_position_benchmark import run_position_suite
from crownline_position_suite import POSITION_SUITE_ID, POSITION_SUITE_PATH


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = 1


def _compact(report) -> dict:
    s = report.summary
    return {
        "complete_scenario_pairs": s["complete_scenario_pairs"],
        "incomplete_scenario_pairs": s["incomplete_scenario_pairs"],
        "complete_sets": s["complete_sets"],
        "repetition_stops": s["repetition_detected_sets"],
        "scenario_pair_wins": s["scenario_pair_wins"],
        "scenario_pair_margins_a_minus_b": s["scenario_pair_margins_a_minus_b"],
        "set_wins": s["set_wins"],
        "aggregate_score_totals": s["aggregate_score_totals"],
        "mean_set_margin_a_minus_b": s["mean_set_margin_a_minus_b"],
        "mean_paired_margin_a_minus_b": s["mean_paired_margin_a_minus_b"],
        "end_reasons": s["end_reasons"],
        "engine_metrics": s["engine_metrics"],
        "repetition_cycle_lengths": s["repetition_cycle_lengths"],
        "repetition_escape_actions": s["repetition_escape_actions"],
    }


def run(*, depth: int, repeat_penalty: float, max_game_plies: int, repetition_limit: int) -> dict:
    baseline = BaselineEngine(f"baseline-d{depth}", depth)
    candidate = RepeatAwareEngine(
        f"repeat-aware-p{repeat_penalty:g}-d{depth}",
        depth,
        repeat_penalty,
    )
    report = run_position_suite(
        baseline,
        candidate,
        suite_id=POSITION_SUITE_ID,
        max_game_plies=max_game_plies,
        repetition_limit=repetition_limit,
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "experiment": "stage3-repeat-aware-head-to-head",
        "suite_id": POSITION_SUITE_ID,
        "rules_mode": "candidate",
        "depth": depth,
        "repeat_penalty": repeat_penalty,
        "max_game_plies": max_game_plies,
        "repetition_limit": repetition_limit,
        "hypothesis": (
            "The smallest penalty from the self-play sweep that reduced repetition from six "
            "stops to two (50 evaluator points) can reduce cycling without sacrificing playing "
            "strength against fixed-depth Baseline A."
        ),
        "engine_a": "Baseline A",
        "engine_b": "Repeat-aware candidate",
        "summary": _compact(report),
        "candidate_history_metrics": {
            "repeat_candidates_seen": candidate.repeat_candidates_seen,
            "decisions_with_repeat_candidate": candidate.decisions_with_repeat_candidate,
            "repeated_action_selected": candidate.repeated_action_selected,
        },
        "report": asdict(report),
        "source_fingerprints": {
            "baseline_ai_sha256": _source_fingerprint("crownline_ai.py"),
            "history_policy_sha256": _source_fingerprint("crownline_history_policy_experiment.py"),
            "benchmark_harness_sha256": _source_fingerprint("crownline_benchmark.py"),
            "position_runner_sha256": _source_fingerprint("crownline_position_benchmark.py"),
            "position_suite_sha256": _source_fingerprint(str(POSITION_SUITE_PATH.relative_to(ROOT))),
            "experiment_sha256": _source_fingerprint("experiments/benchmark_repeat_penalty_head_to_head.py"),
        },
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare repeat-aware Crownline policy against Baseline A.")
    parser.add_argument("--depth", type=int, default=3, choices=range(1, 5))
    parser.add_argument("--repeat-penalty", type=float, default=50.0)
    parser.add_argument("--max-game-plies", type=int, default=300)
    parser.add_argument("--repetition-limit", type=int, default=3)
    parser.add_argument("--json", dest="json_path", default=None)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    report = run(
        depth=args.depth,
        repeat_penalty=args.repeat_penalty,
        max_game_plies=args.max_game_plies,
        repetition_limit=args.repetition_limit,
    )
    s = report["summary"]
    print("Crownline Stage 3 repeat-aware head-to-head")
    print(f"depth={args.depth} repeat_penalty={args.repeat_penalty}")
    print(
        f"complete sets {s['complete_sets']}/16 | repetitions {s['repetition_stops']} | "
        f"complete pairs {s['complete_scenario_pairs']}/8"
    )
    print(f"scenario pair wins {s['scenario_pair_wins']}")
    print(f"set wins {s['set_wins']}")
    print(f"aggregate completed score {s['aggregate_score_totals']}")
    print(f"candidate history {report['candidate_history_metrics']}")
    if args.json_path:
        path = Path(args.json_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"JSON report: {path}")


if __name__ == "__main__":
    main()
