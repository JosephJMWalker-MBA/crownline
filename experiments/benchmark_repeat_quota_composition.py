from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from crownline_benchmark import _source_fingerprint
from crownline_history_policy_experiment import RepeatAwareEngine
from crownline_position_benchmark import run_position_suite
from crownline_position_suite import POSITION_SUITE_ID, POSITION_SUITE_PATH
from crownline_repeat_quota_experiment import RepeatQuotaEngine


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
    }


def _policy_meta(engine) -> dict:
    return {
        "repeat_penalty": getattr(engine, "repeat_penalty", None),
        "repeat_candidates_seen": getattr(engine, "repeat_candidates_seen", 0),
        "decisions_with_repeat_candidate": getattr(engine, "decisions_with_repeat_candidate", 0),
        "repeated_action_selected": getattr(engine, "repeated_action_selected", 0),
        "extend_final_response": getattr(engine, "extend_final_response", False),
        "extended_leaf_states": getattr(engine, "extended_leaf_states", 0),
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
        "engine_a": report.engine_a | _policy_meta(engine_a),
        "engine_b": report.engine_b | _policy_meta(engine_b),
        "summary": _compact(report),
        "report": asdict(report),
    }


def run(*, depth: int, repeat_penalty: float, max_game_plies: int, repetition_limit: int) -> dict:
    history_self = _run_matchup(
        "repeat-aware-self",
        RepeatAwareEngine(f"repeat-p{repeat_penalty:g}-d{depth}-A", depth, repeat_penalty),
        RepeatAwareEngine(f"repeat-p{repeat_penalty:g}-d{depth}-B", depth, repeat_penalty),
        max_game_plies=max_game_plies,
        repetition_limit=repetition_limit,
    )
    composed_self = _run_matchup(
        "repeat-plus-quota-self",
        RepeatQuotaEngine(f"repeat-quota-p{repeat_penalty:g}-d{depth}-A", depth, repeat_penalty, True),
        RepeatQuotaEngine(f"repeat-quota-p{repeat_penalty:g}-d{depth}-B", depth, repeat_penalty, True),
        max_game_plies=max_game_plies,
        repetition_limit=repetition_limit,
    )
    head_to_head = _run_matchup(
        "repeat-aware-vs-repeat-plus-quota",
        RepeatAwareEngine(f"repeat-p{repeat_penalty:g}-d{depth}", depth, repeat_penalty),
        RepeatQuotaEngine(f"repeat-quota-p{repeat_penalty:g}-d{depth}", depth, repeat_penalty, True),
        max_game_plies=max_game_plies,
        repetition_limit=repetition_limit,
    )

    h = history_self["summary"]
    q = composed_self["summary"]
    return {
        "schema_version": SCHEMA_VERSION,
        "experiment": "stage3-repeat-plus-quota-composition",
        "suite_id": POSITION_SUITE_ID,
        "rules_mode": "candidate",
        "depth": depth,
        "repeat_penalty": repeat_penalty,
        "max_game_plies": max_game_plies,
        "repetition_limit": repetition_limit,
        "hypothesis": (
            "The exact final-response horizon extension is best judged after the known "
            "four-ply cycle pathology is partially controlled. Adding it to the measured "
            "50-point actual-history repeat policy should preserve the repeat-policy "
            "completion benefit while improving or at least not degrading paired outcomes."
        ),
        "primary_comparison": {
            "history_complete_sets": h["complete_sets"],
            "composed_complete_sets": q["complete_sets"],
            "complete_set_change": q["complete_sets"] - h["complete_sets"],
            "history_repetition_stops": h["repetition_stops"],
            "composed_repetition_stops": q["repetition_stops"],
            "repetition_stop_change": q["repetition_stops"] - h["repetition_stops"],
            "history_complete_pairs": h["complete_scenario_pairs"],
            "composed_complete_pairs": q["complete_scenario_pairs"],
        },
        "matchups": [history_self, composed_self, head_to_head],
        "source_fingerprints": {
            "baseline_ai_sha256": _source_fingerprint("crownline_ai.py"),
            "history_engine_sha256": _source_fingerprint("crownline_history_policy_experiment.py"),
            "quota_engine_sha256": _source_fingerprint("crownline_quota_horizon_experiment.py"),
            "composed_engine_sha256": _source_fingerprint("crownline_repeat_quota_experiment.py"),
            "benchmark_harness_sha256": _source_fingerprint("crownline_benchmark.py"),
            "position_runner_sha256": _source_fingerprint("crownline_position_benchmark.py"),
            "position_suite_sha256": _source_fingerprint(str(POSITION_SUITE_PATH.relative_to(ROOT))),
            "experiment_sha256": _source_fingerprint("experiments/benchmark_repeat_quota_composition.py"),
        },
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Measure quota horizon extension on top of the Stage-3 repeat-aware policy."
    )
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
    print("Crownline Stage 3 repeat-policy + quota-horizon composition")
    print(f"depth={report['depth']} repeat_penalty={report['repeat_penalty']}")
    for matchup in report["matchups"]:
        s = matchup["summary"]
        print(
            f"{matchup['name']}: complete {s['complete_sets']}/16 | "
            f"repetitions {s['repetition_stops']} | pairs {s['complete_scenario_pairs']}/8 | "
            f"pair wins {s['scenario_pair_wins']} | "
            f"extensions A/B {matchup['engine_a']['extended_leaf_states']}/"
            f"{matchup['engine_b']['extended_leaf_states']}"
        )
    p = report["primary_comparison"]
    print(
        "self-play: complete "
        f"{p['history_complete_sets']} -> {p['composed_complete_sets']} | "
        f"repetition {p['history_repetition_stops']} -> {p['composed_repetition_stops']}"
    )
    if args.json_path:
        path = Path(args.json_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"JSON report: {path}")


if __name__ == "__main__":
    main()
