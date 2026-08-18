from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from crownline_benchmark import _source_fingerprint
from crownline_maturity_product_candidate import RepeatAwareMaturityStructuralTTOpponent
from crownline_position_benchmark import run_position_suite
from crownline_position_suite import POSITION_SUITE_ID, POSITION_SUITE_PATH
from crownline_product_candidate import RepeatAwareStructuralTTOpponent


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
        "repeat_penalty": engine.repeat_penalty,
        "maturity_weight": getattr(engine, "maturity_weight", 0.0),
        "decisions": engine.decisions,
        "mean_completed_depth": engine.mean_completed_depth,
        "timed_out_decisions": engine.timed_out_decisions,
        "repeat_candidates_seen": engine.repeat_candidates_seen,
        "decisions_with_repeat_candidate": engine.decisions_with_repeat_candidate,
        "repeated_action_selected": engine.repeated_action_selected,
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


def _p200(name: str, budget_ms: float, max_depth: int, repeat_penalty: float):
    return RepeatAwareStructuralTTOpponent(
        name=name,
        budget_ms=budget_ms,
        max_depth=max_depth,
        repeat_penalty=repeat_penalty,
    )


def _composed(name: str, budget_ms: float, max_depth: int, repeat_penalty: float, maturity_weight: float):
    return RepeatAwareMaturityStructuralTTOpponent(
        name=name,
        budget_ms=budget_ms,
        max_depth=max_depth,
        repeat_penalty=repeat_penalty,
        maturity_weight=maturity_weight,
    )


def run(*, budget_ms: float, max_depth: int, repeat_penalty: float, maturity_weight: float, max_game_plies: int, repetition_limit: int) -> dict:
    p200_self = _run_matchup(
        "p200-control-self",
        _p200("p200-control-A", budget_ms, max_depth, repeat_penalty),
        _p200("p200-control-B", budget_ms, max_depth, repeat_penalty),
        max_game_plies=max_game_plies,
        repetition_limit=repetition_limit,
    )
    composed_self = _run_matchup(
        "p200-plus-maturity-self",
        _composed("p200-maturity-A", budget_ms, max_depth, repeat_penalty, maturity_weight),
        _composed("p200-maturity-B", budget_ms, max_depth, repeat_penalty, maturity_weight),
        max_game_plies=max_game_plies,
        repetition_limit=repetition_limit,
    )
    head_to_head = _run_matchup(
        "p200-control-vs-p200-plus-maturity",
        _p200("p200-control", budget_ms, max_depth, repeat_penalty),
        _composed("p200-maturity", budget_ms, max_depth, repeat_penalty, maturity_weight),
        max_game_plies=max_game_plies,
        repetition_limit=repetition_limit,
    )

    control = p200_self["summary"]
    candidate = composed_self["summary"]
    return {
        "schema_version": SCHEMA_VERSION,
        "experiment": "stage3-p200-plus-promotion-maturity-150ms-composition",
        "suite_id": POSITION_SUITE_ID,
        "rules_mode": "candidate",
        "runtime_semantics": "wall-clock-deadline-sensitive",
        "budget_ms": budget_ms,
        "max_depth": max_depth,
        "repeat_penalty": repeat_penalty,
        "maturity_weight": maturity_weight,
        "max_game_plies": max_game_plies,
        "repetition_limit": repetition_limit,
        "hypothesis": (
            "Promotion maturity w10 survived fixed-depth and 150 ms policy-stability gates. "
            "Holding the current p200 exact-history trajectory policy and 150 ms structural-TT "
            "search fixed, adding only maturity w10 should improve or preserve completion and paired "
            "outcomes without materially reducing completed search depth."
        ),
        "primary_comparison": {
            "p200_complete_sets": control["complete_sets"],
            "composed_complete_sets": candidate["complete_sets"],
            "complete_set_change": candidate["complete_sets"] - control["complete_sets"],
            "p200_repetition_stops": control["repetition_stops"],
            "composed_repetition_stops": candidate["repetition_stops"],
            "repetition_stop_change": candidate["repetition_stops"] - control["repetition_stops"],
            "p200_complete_pairs": control["complete_scenario_pairs"],
            "composed_complete_pairs": candidate["complete_scenario_pairs"],
            "p200_mean_depth_a": p200_self["engine_a"]["mean_completed_depth"],
            "p200_mean_depth_b": p200_self["engine_b"]["mean_completed_depth"],
            "composed_mean_depth_a": composed_self["engine_a"]["mean_completed_depth"],
            "composed_mean_depth_b": composed_self["engine_b"]["mean_completed_depth"],
        },
        "matchups": [p200_self, composed_self, head_to_head],
        "source_fingerprints": {
            "baseline_ai_sha256": _source_fingerprint("crownline_ai.py"),
            "product_candidate_sha256": _source_fingerprint("crownline_product_candidate.py"),
            "maturity_feature_sha256": _source_fingerprint("crownline_promotion_maturity_experiment.py"),
            "maturity_time_engine_sha256": _source_fingerprint("crownline_maturity_time_engine.py"),
            "composed_candidate_sha256": _source_fingerprint("crownline_maturity_product_candidate.py"),
            "position_runner_sha256": _source_fingerprint("crownline_position_benchmark.py"),
            "position_suite_sha256": _source_fingerprint(str(POSITION_SUITE_PATH.relative_to(ROOT))),
            "experiment_sha256": _source_fingerprint("experiments/benchmark_maturity_p200_composition_150ms.py"),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark p200 plus promotion maturity w10 at 150 ms.")
    parser.add_argument("--budget-ms", type=float, default=150.0)
    parser.add_argument("--max-depth", type=int, default=4, choices=range(1, 5))
    parser.add_argument("--repeat-penalty", type=float, default=200.0)
    parser.add_argument("--maturity-weight", type=float, default=10.0)
    parser.add_argument("--max-game-plies", type=int, default=300)
    parser.add_argument("--repetition-limit", type=int, default=3)
    parser.add_argument("--json", dest="json_path", default=None)
    args = parser.parse_args()

    report = run(
        budget_ms=args.budget_ms,
        max_depth=args.max_depth,
        repeat_penalty=args.repeat_penalty,
        maturity_weight=args.maturity_weight,
        max_game_plies=args.max_game_plies,
        repetition_limit=args.repetition_limit,
    )
    print("Crownline p200 + promotion maturity 150 ms composition benchmark")
    print(
        f"budget={report['budget_ms']} ms max_depth={report['max_depth']} "
        f"repeat={report['repeat_penalty']} maturity={report['maturity_weight']}"
    )
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
        f"self-play: complete {p['p200_complete_sets']} -> {p['composed_complete_sets']} | "
        f"repetition {p['p200_repetition_stops']} -> {p['composed_repetition_stops']}"
    )

    if args.json_path:
        path = Path(args.json_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"JSON report: {path}")


if __name__ == "__main__":
    main()
