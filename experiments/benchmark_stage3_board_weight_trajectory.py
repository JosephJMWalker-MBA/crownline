from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from crownline_benchmark import BaselineEngine, _source_fingerprint
from crownline_evaluator_experiments import BoardWeightedEngine
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
            "board_weight": getattr(engine_a, "board_weight", 1.0),
        },
        "engine_b": report.engine_b | {
            "board_weight": getattr(engine_b, "board_weight", 1.0),
        },
        "summary": _compact(report),
        "report": asdict(report),
    }


def run(*, depth: int, board_weight: float, max_game_plies: int, repetition_limit: int) -> dict:
    baseline_self = _run_matchup(
        "baseline-d3-self",
        BaselineEngine(f"baseline-d{depth}-A", depth),
        BaselineEngine(f"baseline-d{depth}-B", depth),
        max_game_plies=max_game_plies,
        repetition_limit=repetition_limit,
    )
    candidate_self = _run_matchup(
        "board-weighted-self",
        BoardWeightedEngine(f"board-w{board_weight:g}-d{depth}-A", depth, board_weight),
        BoardWeightedEngine(f"board-w{board_weight:g}-d{depth}-B", depth, board_weight),
        max_game_plies=max_game_plies,
        repetition_limit=repetition_limit,
    )
    head_to_head = _run_matchup(
        "baseline-vs-board-weighted",
        BaselineEngine(f"baseline-d{depth}", depth),
        BoardWeightedEngine(f"board-w{board_weight:g}-d{depth}", depth, board_weight),
        max_game_plies=max_game_plies,
        repetition_limit=repetition_limit,
    )

    b_rep = baseline_self["summary"]["repetition_stops"]
    c_rep = candidate_self["summary"]["repetition_stops"]
    b_complete = baseline_self["summary"]["complete_sets"]
    c_complete = candidate_self["summary"]["complete_sets"]

    return {
        "schema_version": SCHEMA_VERSION,
        "experiment": "stage3-board-value-full-trajectory",
        "suite_id": POSITION_SUITE_ID,
        "rules_mode": "candidate",
        "depth": depth,
        "board_weight": board_weight,
        "max_game_plies": max_game_plies,
        "repetition_limit": repetition_limit,
        "hypothesis": (
            "Reducing only nonterminal board-square value to the Stage 3.1 candidate weight "
            "reduces exact reversible-cycle stops over complete frozen-suite trajectories, "
            "without requiring a direct anti-repetition rule or changing Crownline scoring."
        ),
        "primary_comparison": {
            "baseline_self_repetition_stops": b_rep,
            "candidate_self_repetition_stops": c_rep,
            "repetition_stop_change": c_rep - b_rep,
            "baseline_self_complete_sets": b_complete,
            "candidate_self_complete_sets": c_complete,
            "complete_set_change": c_complete - b_complete,
        },
        "matchups": [baseline_self, candidate_self, head_to_head],
        "source_fingerprints": {
            "baseline_ai_sha256": _source_fingerprint("crownline_ai.py"),
            "experimental_evaluator_sha256": _source_fingerprint("crownline_evaluator_experiments.py"),
            "benchmark_harness_sha256": _source_fingerprint("crownline_benchmark.py"),
            "position_runner_sha256": _source_fingerprint("crownline_position_benchmark.py"),
            "position_suite_sha256": _source_fingerprint(str(POSITION_SUITE_PATH.relative_to(ROOT))),
            "experiment_sha256": _source_fingerprint("experiments/benchmark_stage3_board_weight_trajectory.py"),
        },
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Stage 3 board-value candidate over complete frozen-suite trajectories.")
    parser.add_argument("--depth", type=int, default=3, choices=range(1, 5))
    parser.add_argument("--board-weight", type=float, default=0.25)
    parser.add_argument("--max-game-plies", type=int, default=300)
    parser.add_argument("--repetition-limit", type=int, default=3)
    parser.add_argument("--json", dest="json_path", default=None)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    report = run(
        depth=args.depth,
        board_weight=args.board_weight,
        max_game_plies=args.max_game_plies,
        repetition_limit=args.repetition_limit,
    )
    print("Crownline Stage 3 board-value full-trajectory benchmark")
    print(f"depth={report['depth']} board_weight={report['board_weight']}")
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
        f"{p['baseline_self_repetition_stops']} -> {p['candidate_self_repetition_stops']} "
        f"({p['repetition_stop_change']:+d})"
    )
    if args.json_path:
        path = Path(args.json_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"JSON report: {path}")


if __name__ == "__main__":
    main()
