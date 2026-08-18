from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from crownline_benchmark import _source_fingerprint
from crownline_maturity_time_engine import PromotionMaturityStructuralTTTimeControl
from crownline_position_benchmark import run_position_suite
from crownline_position_suite import POSITION_SUITE_ID, POSITION_SUITE_PATH
from crownline_product_candidate import StructuralTTTimeControl


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
        "budget_ms": engine.budget_ms,
        "max_depth": engine.max_depth,
        "decisions": engine.decisions,
        "mean_completed_depth": engine.mean_completed_depth,
        "timed_out_decisions": engine.timed_out_decisions,
        "maturity_weight": getattr(engine, "maturity_weight", 0.0),
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


def _maturity(name: str, budget_ms: float, max_depth: int, maturity_weight: float):
    return PromotionMaturityStructuralTTTimeControl(
        name=name,
        budget_ms=budget_ms,
        max_depth=max_depth,
        maturity_weight=maturity_weight,
    )


def run(*, budget_ms: float, max_depth: int, maturity_weight: float, max_game_plies: int, repetition_limit: int) -> dict:
    control_self = _run_matchup(
        "stage2-control-self",
        _control("stage2-control-A", budget_ms, max_depth),
        _control("stage2-control-B", budget_ms, max_depth),
        max_game_plies=max_game_plies,
        repetition_limit=repetition_limit,
    )
    maturity_self = _run_matchup(
        "maturity-w10-self",
        _maturity("maturity-A", budget_ms, max_depth, maturity_weight),
        _maturity("maturity-B", budget_ms, max_depth, maturity_weight),
        max_game_plies=max_game_plies,
        repetition_limit=repetition_limit,
    )
    head_to_head = _run_matchup(
        "stage2-control-vs-maturity",
        _control("stage2-control", budget_ms, max_depth),
        _maturity("maturity", budget_ms, max_depth, maturity_weight),
        max_game_plies=max_game_plies,
        repetition_limit=repetition_limit,
    )

    control = control_self["summary"]
    maturity = maturity_self["summary"]
    return {
        "schema_version": SCHEMA_VERSION,
        "experiment": "stage3-promotion-maturity-150ms-search-regime-transfer",
        "suite_id": POSITION_SUITE_ID,
        "rules_mode": "candidate",
        "budget_ms": budget_ms,
        "max_depth": max_depth,
        "maturity_weight": maturity_weight,
        "max_game_plies": max_game_plies,
        "repetition_limit": repetition_limit,
        "hypothesis": (
            "Promotion maturity w10 improved fixed-depth-3 completion and direct paired outcomes. "
            "Holding the 150 ms iterative structural-TT search substrate fixed, substituting only "
            "the maturity evaluator should preserve that benefit without materially reducing "
            "completed search depth or introducing a new trajectory pathology."
        ),
        "primary_comparison": {
            "control_complete_sets": control["complete_sets"],
            "maturity_complete_sets": maturity["complete_sets"],
            "complete_set_change": maturity["complete_sets"] - control["complete_sets"],
            "control_repetition_stops": control["repetition_stops"],
            "maturity_repetition_stops": maturity["repetition_stops"],
            "repetition_stop_change": maturity["repetition_stops"] - control["repetition_stops"],
            "control_complete_pairs": control["complete_scenario_pairs"],
            "maturity_complete_pairs": maturity["complete_scenario_pairs"],
            "control_mean_depth_a": control_self["engine_a"]["mean_completed_depth"],
            "control_mean_depth_b": control_self["engine_b"]["mean_completed_depth"],
            "maturity_mean_depth_a": maturity_self["engine_a"]["mean_completed_depth"],
            "maturity_mean_depth_b": maturity_self["engine_b"]["mean_completed_depth"],
        },
        "matchups": [control_self, maturity_self, head_to_head],
        "source_fingerprints": {
            "baseline_ai_sha256": _source_fingerprint("crownline_ai.py"),
            "stage2_tt_time_engine_sha256": _source_fingerprint("crownline_tt_time_engine.py"),
            "maturity_feature_sha256": _source_fingerprint("crownline_promotion_maturity_experiment.py"),
            "maturity_time_engine_sha256": _source_fingerprint("crownline_maturity_time_engine.py"),
            "position_runner_sha256": _source_fingerprint("crownline_position_benchmark.py"),
            "position_suite_sha256": _source_fingerprint(str(POSITION_SUITE_PATH.relative_to(ROOT))),
            "experiment_sha256": _source_fingerprint("experiments/benchmark_maturity_transfer_150ms.py"),
        },
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Benchmark promotion maturity w10 inside the 150 ms structural-TT product regime.")
    parser.add_argument("--budget-ms", type=float, default=150.0)
    parser.add_argument("--max-depth", type=int, default=4, choices=range(1, 5))
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
        budget_ms=args.budget_ms,
        max_depth=args.max_depth,
        maturity_weight=args.maturity_weight,
        max_game_plies=args.max_game_plies,
        repetition_limit=args.repetition_limit,
    )
    print("Crownline promotion-maturity 150 ms transfer benchmark")
    print(f"budget={report['budget_ms']} ms max_depth={report['max_depth']} maturity={report['maturity_weight']}")
    for matchup in report["matchups"]:
        s = matchup["summary"]
        print(
            f"{matchup['name']}: complete {s['complete_sets']}/16 | repetitions {s['repetition_stops']} | "
            f"pairs {s['complete_scenario_pairs']}/8 | pair wins {s['scenario_pair_wins']} | "
            f"mean depth A/B {matchup['engine_a']['mean_completed_depth']:.2f}/"
            f"{matchup['engine_b']['mean_completed_depth']:.2f}"
        )
    p = report["primary_comparison"]
    print(
        f"self-play: complete {p['control_complete_sets']} -> {p['maturity_complete_sets']} | "
        f"repetition {p['control_repetition_stops']} -> {p['maturity_repetition_stops']}"
    )
    if args.json_path:
        path = Path(args.json_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"JSON report: {path}")


if __name__ == "__main__":
    main()
