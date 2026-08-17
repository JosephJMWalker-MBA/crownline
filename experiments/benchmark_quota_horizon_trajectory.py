from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

import crownline_ai
from crownline_benchmark import BaselineEngine, _source_fingerprint
from crownline_position_benchmark import run_position_suite
from crownline_position_suite import POSITION_SUITE_ID, POSITION_SUITE_PATH, position_suite
from crownline_quota_horizon_experiment import QuotaHorizonEngine, choose_quota_horizon_action
from crownline_set import CrownlineSet


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = 1


def _state_for_fixture(fixture) -> CrownlineSet:
    return CrownlineSet(
        first_game_white="A",
        current_game=fixture.game(),
        rules_mode="candidate",
    )


def _frozen_root_diagnostic(depth: int) -> dict:
    changes = []
    for scenario in position_suite():
        for label, fixture in (("game1", scenario.game1), ("game2", scenario.game2)):
            state = _state_for_fixture(fixture)
            participant = state.participant_for_color(state.current_game.turn)
            baseline = crownline_ai.choose_computer_action(
                state,
                participant=participant,
                depth=depth,
            )
            candidate = choose_quota_horizon_action(
                state,
                participant,
                depth=depth,
                extend_final_response=True,
            )
            if candidate != baseline:
                changes.append(
                    {
                        "scenario_id": scenario.scenario_id,
                        "fixture": label,
                        "participant": participant,
                        "baseline": {
                            "move": baseline[0],
                            "meld_line": baseline[1],
                        },
                        "quota_horizon": {
                            "move": candidate[0],
                            "meld_line": candidate[1],
                        },
                    }
                )
    return {
        "positions": 16,
        "changed_actions": len(changes),
        "unchanged_actions": 16 - len(changes),
        "changes": changes,
    }


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


def _engine_experiment_meta(engine) -> dict:
    return {
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
        "engine_a": report.engine_a | _engine_experiment_meta(engine_a),
        "engine_b": report.engine_b | _engine_experiment_meta(engine_b),
        "summary": _compact(report),
        "report": asdict(report),
    }


def run(*, depth: int, max_game_plies: int, repetition_limit: int) -> dict:
    root_diagnostic = _frozen_root_diagnostic(depth)

    baseline_self = _run_matchup(
        "baseline-self",
        BaselineEngine(f"baseline-d{depth}-A", depth),
        BaselineEngine(f"baseline-d{depth}-B", depth),
        max_game_plies=max_game_plies,
        repetition_limit=repetition_limit,
    )
    quota_self = _run_matchup(
        "quota-horizon-self",
        QuotaHorizonEngine(f"quota-horizon-d{depth}-A", depth, True),
        QuotaHorizonEngine(f"quota-horizon-d{depth}-B", depth, True),
        max_game_plies=max_game_plies,
        repetition_limit=repetition_limit,
    )
    head_to_head = _run_matchup(
        "baseline-vs-quota-horizon",
        BaselineEngine(f"baseline-d{depth}", depth),
        QuotaHorizonEngine(f"quota-horizon-d{depth}", depth, True),
        max_game_plies=max_game_plies,
        repetition_limit=repetition_limit,
    )

    baseline_rep = baseline_self["summary"]["repetition_stops"]
    quota_rep = quota_self["summary"]["repetition_stops"]
    baseline_complete = baseline_self["summary"]["complete_sets"]
    quota_complete = quota_self["summary"]["complete_sets"]

    return {
        "schema_version": SCHEMA_VERSION,
        "experiment": "stage3-quota-final-response-horizon",
        "suite_id": POSITION_SUITE_ID,
        "rules_mode": "candidate",
        "depth": depth,
        "max_game_plies": max_game_plies,
        "repetition_limit": repetition_limit,
        "hypothesis": (
            "Baseline A can cut off search on the unique nonterminal state after the capture "
            "quota has been crossed but before the opponent's mandatory final response. "
            "Resolving exactly that one rule-forced response at the horizon should improve "
            "quota tactics without altering the static evaluator or unrelated positions."
        ),
        "frozen_root_diagnostic": root_diagnostic,
        "primary_comparison": {
            "baseline_self_repetition_stops": baseline_rep,
            "quota_self_repetition_stops": quota_rep,
            "repetition_stop_change": quota_rep - baseline_rep,
            "baseline_self_complete_sets": baseline_complete,
            "quota_self_complete_sets": quota_complete,
            "complete_set_change": quota_complete - baseline_complete,
            "frozen_root_action_changes": root_diagnostic["changed_actions"],
        },
        "matchups": [baseline_self, quota_self, head_to_head],
        "source_fingerprints": {
            "baseline_ai_sha256": _source_fingerprint("crownline_ai.py"),
            "quota_horizon_engine_sha256": _source_fingerprint("crownline_quota_horizon_experiment.py"),
            "benchmark_harness_sha256": _source_fingerprint("crownline_benchmark.py"),
            "position_runner_sha256": _source_fingerprint("crownline_position_benchmark.py"),
            "position_suite_sha256": _source_fingerprint(str(POSITION_SUITE_PATH.relative_to(ROOT))),
            "experiment_sha256": _source_fingerprint("experiments/benchmark_quota_horizon_trajectory.py"),
        },
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Test a one-ply final-response horizon extension on Crownline's frozen suite."
    )
    parser.add_argument("--depth", type=int, default=3, choices=range(1, 5))
    parser.add_argument("--max-game-plies", type=int, default=300)
    parser.add_argument("--repetition-limit", type=int, default=3)
    parser.add_argument("--json", dest="json_path", default=None)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    report = run(
        depth=args.depth,
        max_game_plies=args.max_game_plies,
        repetition_limit=args.repetition_limit,
    )
    print("Crownline Stage 3 quota/final-response horizon benchmark")
    print(f"depth={report['depth']}")
    root = report["frozen_root_diagnostic"]
    print(
        f"frozen root actions changed: {root['changed_actions']}/{root['positions']}"
    )
    for matchup in report["matchups"]:
        s = matchup["summary"]
        print(
            f"{matchup['name']}: complete sets {s['complete_sets']}/16 | "
            f"repetition stops {s['repetition_stops']} | "
            f"scenario pairs {s['complete_scenario_pairs']}/8 | "
            f"pair wins {s['scenario_pair_wins']} | "
            f"extensions A/B {matchup['engine_a']['extended_leaf_states']}/"
            f"{matchup['engine_b']['extended_leaf_states']}"
        )
    if root["changes"]:
        print("changed frozen roots:")
        for change in root["changes"]:
            print(
                f"  {change['scenario_id']} {change['fixture']}: "
                f"{change['baseline']['move']} -> {change['quota_horizon']['move']}"
            )
    p = report["primary_comparison"]
    print(
        "self-play completion/repetition: "
        f"{p['baseline_self_complete_sets']}/{16}, rep {p['baseline_self_repetition_stops']} -> "
        f"{p['quota_self_complete_sets']}/{16}, rep {p['quota_self_repetition_stops']}"
    )
    if args.json_path:
        path = Path(args.json_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"JSON report: {path}")


if __name__ == "__main__":
    main()
