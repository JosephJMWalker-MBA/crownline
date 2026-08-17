from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from crownline_benchmark import BaselineEngine, _source_fingerprint
from crownline_position_benchmark import run_position_suite
from crownline_position_suite import POSITION_SUITE_ID, POSITION_SUITE_PATH
from crownline_promotion_maturity_experiment import PromotionMaturityEngine


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
        "maturity_weight": getattr(engine, "maturity_weight", 0.0),
    }


def _run_matchup(
    name: str,
    engine_a,
    engine_b,
    *,
    max_game_plies: int,
    repetition_limit: int,
) -> dict:
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


def run(
    *,
    depth: int,
    maturity_weight: float,
    max_game_plies: int,
    repetition_limit: int,
) -> dict:
    baseline_self = _run_matchup(
        "baseline-self",
        BaselineEngine(f"baseline-d{depth}-A", depth),
        BaselineEngine(f"baseline-d{depth}-B", depth),
        max_game_plies=max_game_plies,
        repetition_limit=repetition_limit,
    )
    maturity_self = _run_matchup(
        "promotion-maturity-self",
        PromotionMaturityEngine(
            f"maturity-w{maturity_weight:g}-d{depth}-A",
            depth,
            maturity_weight,
        ),
        PromotionMaturityEngine(
            f"maturity-w{maturity_weight:g}-d{depth}-B",
            depth,
            maturity_weight,
        ),
        max_game_plies=max_game_plies,
        repetition_limit=repetition_limit,
    )
    head_to_head = _run_matchup(
        "baseline-vs-promotion-maturity",
        BaselineEngine(f"baseline-d{depth}", depth),
        PromotionMaturityEngine(
            f"maturity-w{maturity_weight:g}-d{depth}",
            depth,
            maturity_weight,
        ),
        max_game_plies=max_game_plies,
        repetition_limit=repetition_limit,
    )

    baseline = baseline_self["summary"]
    candidate = maturity_self["summary"]
    return {
        "schema_version": SCHEMA_VERSION,
        "experiment": "stage3-promotion-maturity-full-trajectory",
        "suite_id": POSITION_SUITE_ID,
        "rules_mode": "candidate",
        "depth": depth,
        "maturity_weight": maturity_weight,
        "max_game_plies": max_game_plies,
        "repetition_limit": repetition_limit,
        "hypothesis": (
            "The smallest continuous promotion-maturity weight that removes one additional "
            "preserved depth-3 cycle choice while changing 0/16 early roots and only 1/12 "
            "King hard cases should be tested over complete trajectories before any strategic "
            "claim. Unlike pure proximity, maturity keeps realized promotion value at King=1.0, "
            "so the trajectory test must verify it does not suppress actual promotions."
        ),
        "primary_comparison": {
            "baseline_complete_sets": baseline["complete_sets"],
            "candidate_complete_sets": candidate["complete_sets"],
            "complete_set_change": candidate["complete_sets"] - baseline["complete_sets"],
            "baseline_repetition_stops": baseline["repetition_stops"],
            "candidate_repetition_stops": candidate["repetition_stops"],
            "repetition_stop_change": candidate["repetition_stops"] - baseline["repetition_stops"],
            "baseline_complete_pairs": baseline["complete_scenario_pairs"],
            "candidate_complete_pairs": candidate["complete_scenario_pairs"],
        },
        "matchups": [baseline_self, maturity_self, head_to_head],
        "source_fingerprints": {
            "baseline_ai_sha256": _source_fingerprint("crownline_ai.py"),
            "maturity_experiment_sha256": _source_fingerprint(
                "crownline_promotion_maturity_experiment.py"
            ),
            "benchmark_harness_sha256": _source_fingerprint("crownline_benchmark.py"),
            "position_runner_sha256": _source_fingerprint("crownline_position_benchmark.py"),
            "position_suite_sha256": _source_fingerprint(
                str(POSITION_SUITE_PATH.relative_to(ROOT))
            ),
            "experiment_sha256": _source_fingerprint(
                "experiments/benchmark_promotion_maturity_trajectory.py"
            ),
        },
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the continuous promotion-maturity evaluator over frozen full trajectories."
    )
    parser.add_argument("--depth", type=int, default=3, choices=range(1, 5))
    parser.add_argument("--maturity-weight", type=float, default=10.0)
    parser.add_argument("--max-game-plies", type=int, default=300)
    parser.add_argument("--repetition-limit", type=int, default=3)
    parser.add_argument("--json", dest="json_path", default=None)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    if args.maturity_weight < 0:
        raise SystemExit("maturity weight must be non-negative")
    report = run(
        depth=args.depth,
        maturity_weight=args.maturity_weight,
        max_game_plies=args.max_game_plies,
        repetition_limit=args.repetition_limit,
    )
    print("Crownline Stage 3 promotion-maturity full-trajectory benchmark")
    print(f"depth={report['depth']} maturity_weight={report['maturity_weight']}")
    for matchup in report["matchups"]:
        summary = matchup["summary"]
        print(
            f"{matchup['name']}: complete {summary['complete_sets']}/16 | "
            f"repetitions {summary['repetition_stops']} | "
            f"pairs {summary['complete_scenario_pairs']}/8 | "
            f"pair wins {summary['scenario_pair_wins']}"
        )
    primary = report["primary_comparison"]
    print(
        "self-play: complete "
        f"{primary['baseline_complete_sets']} -> {primary['candidate_complete_sets']} | "
        f"repetition {primary['baseline_repetition_stops']} -> "
        f"{primary['candidate_repetition_stops']}"
    )
    if args.json_path:
        path = Path(args.json_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(f"JSON report: {path}")


if __name__ == "__main__":
    main()
