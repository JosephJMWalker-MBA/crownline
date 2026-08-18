from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from statistics import mean

from crownline_benchmark import _source_fingerprint
from crownline_maturity_time_engine import choose_computer_action_iterative_structural_tt_maturity
from crownline_position_suite import POSITION_SUITE_PATH, position_suite
from crownline_set import CrownlineSet
from crownline_tt_time_engine import choose_computer_action_iterative_structural_tt


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = 1


def _state(fixture) -> CrownlineSet:
    return CrownlineSet(
        first_game_white="A",
        current_game=fixture.game(),
        rules_mode="candidate",
    )


def _label(notation, meld_line) -> str:
    return notation + (f" | {'-'.join(meld_line)}" if meld_line else "")


def _one(engine: str, state: CrownlineSet, participant: str, budget_ms: float, max_depth: int, maturity_weight: float) -> dict:
    if engine == "control":
        notation, meld_line, stats = choose_computer_action_iterative_structural_tt(
            state,
            participant=participant,
            budget_ms=budget_ms,
            max_depth=max_depth,
        )
    elif engine == "maturity":
        notation, meld_line, stats = choose_computer_action_iterative_structural_tt_maturity(
            state,
            participant=participant,
            budget_ms=budget_ms,
            max_depth=max_depth,
            maturity_weight=maturity_weight,
        )
    else:
        raise ValueError(engine)
    return {
        "action": _label(notation, meld_line),
        "completed_depth": stats.completed_depth,
        "attempted_depth": stats.attempted_depth,
        "timed_out": stats.timed_out,
        "elapsed_ms": stats.elapsed_ms,
        "expanded_nodes": stats.total_expanded_nodes,
    }


def _engine_summary(rows: list[dict], max_depth: int) -> dict:
    by_fixture: dict[str, list[dict]] = {}
    for row in rows:
        by_fixture.setdefault(row["fixture_id"], []).append(row)

    fixture_summaries = []
    for fixture_id, items in sorted(by_fixture.items()):
        action_counts = Counter(item["action"] for item in items)
        depth_counts = Counter(item["completed_depth"] for item in items)
        fixture_summaries.append(
            {
                "fixture_id": fixture_id,
                "decision_count": len(items),
                "unique_actions": len(action_counts),
                "action_counts": dict(sorted(action_counts.items())),
                "unique_completed_depths": len(depth_counts),
                "completed_depth_counts": {str(k): v for k, v in sorted(depth_counts.items())},
                "mean_completed_depth": mean(item["completed_depth"] for item in items),
                "mean_elapsed_ms": mean(item["elapsed_ms"] for item in items),
            }
        )

    depth_counts = Counter(row["completed_depth"] for row in rows)
    return {
        "decisions": len(rows),
        "positions": len(by_fixture),
        "positions_with_action_variation": sum(item["unique_actions"] > 1 for item in fixture_summaries),
        "positions_with_depth_variation": sum(item["unique_completed_depths"] > 1 for item in fixture_summaries),
        "completed_depth_counts": {str(k): v for k, v in sorted(depth_counts.items())},
        "mean_completed_depth": mean(row["completed_depth"] for row in rows),
        "full_depth_rate": sum(row["completed_depth"] == max_depth for row in rows) / len(rows),
        "mean_elapsed_ms": mean(row["elapsed_ms"] for row in rows),
        "mean_expanded_nodes": mean(row["expanded_nodes"] for row in rows),
        "fixtures": fixture_summaries,
    }


def run(*, repeats: int, budget_ms: float, max_depth: int, maturity_weight: float) -> dict:
    if repeats < 2:
        raise ValueError("repeats must be at least 2")

    control_rows: list[dict] = []
    maturity_rows: list[dict] = []
    same_rep_pairs = []

    fixtures = []
    for scenario in position_suite():
        fixtures.append((f"{scenario.scenario_id}:game1", scenario.game1))
        fixtures.append((f"{scenario.scenario_id}:game2", scenario.game2))

    for fixture_id, fixture in fixtures:
        state = _state(fixture)
        participant = state.participant_for_color(state.current_game.turn)
        for repeat in range(repeats):
            # Alternate order so one engine does not always receive the warmer CPU/cache state.
            order = ("control", "maturity") if repeat % 2 == 0 else ("maturity", "control")
            results = {}
            for engine in order:
                result = _one(
                    engine,
                    state,
                    participant,
                    budget_ms,
                    max_depth,
                    maturity_weight,
                )
                row = {
                    "fixture_id": fixture_id,
                    "repeat": repeat + 1,
                    "order_index": order.index(engine),
                    **result,
                }
                results[engine] = result
                (control_rows if engine == "control" else maturity_rows).append(row)
            same_rep_pairs.append(
                {
                    "fixture_id": fixture_id,
                    "repeat": repeat + 1,
                    "same_action": results["control"]["action"] == results["maturity"]["action"],
                    "control_action": results["control"]["action"],
                    "maturity_action": results["maturity"]["action"],
                    "control_depth": results["control"]["completed_depth"],
                    "maturity_depth": results["maturity"]["completed_depth"],
                }
            )

    control = _engine_summary(control_rows, max_depth)
    maturity = _engine_summary(maturity_rows, max_depth)
    return {
        "schema_version": SCHEMA_VERSION,
        "experiment": "stage3-150ms-wall-clock-stability-audit",
        "rules_mode": "candidate",
        "repeats": repeats,
        "budget_ms": budget_ms,
        "max_depth": max_depth,
        "maturity_weight": maturity_weight,
        "position_count": len(fixtures),
        "hypothesis": (
            "Wall-clock iterative deepening is deadline-sensitive rather than trajectory-deterministic. "
            "Repeating the exact same frozen CLSN roots should quantify how often runtime jitter changes "
            "completed depth or the selected action, and whether the maturity evaluator materially "
            "changes that sensitivity."
        ),
        "control": control,
        "maturity": maturity,
        "cross_engine": {
            "same_rep_decisions": len(same_rep_pairs),
            "same_action_count": sum(item["same_action"] for item in same_rep_pairs),
            "same_action_rate": sum(item["same_action"] for item in same_rep_pairs) / len(same_rep_pairs),
            "pairs": same_rep_pairs,
        },
        "source_fingerprints": {
            "stage2_tt_time_engine_sha256": _source_fingerprint("crownline_tt_time_engine.py"),
            "maturity_time_engine_sha256": _source_fingerprint("crownline_maturity_time_engine.py"),
            "position_suite_sha256": _source_fingerprint(str(POSITION_SUITE_PATH.relative_to(ROOT))),
            "experiment_sha256": _source_fingerprint("experiments/benchmark_time_budget_stability.py"),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit 150 ms Crownline root-decision stability under repeated wall-clock runs.")
    parser.add_argument("--repeats", type=int, default=6)
    parser.add_argument("--budget-ms", type=float, default=150.0)
    parser.add_argument("--max-depth", type=int, default=4, choices=range(1, 5))
    parser.add_argument("--maturity-weight", type=float, default=10.0)
    parser.add_argument("--json", dest="json_path", default=None)
    args = parser.parse_args()

    report = run(
        repeats=args.repeats,
        budget_ms=args.budget_ms,
        max_depth=args.max_depth,
        maturity_weight=args.maturity_weight,
    )
    print("Crownline 150 ms wall-clock stability audit")
    print(f"positions={report['position_count']} repeats={report['repeats']} budget={report['budget_ms']} ms")
    for name in ("control", "maturity"):
        s = report[name]
        print(
            f"{name}: action-variant positions {s['positions_with_action_variation']}/{s['positions']} | "
            f"depth-variant positions {s['positions_with_depth_variation']}/{s['positions']} | "
            f"mean depth {s['mean_completed_depth']:.3f} | full-depth {s['full_depth_rate']:.1%}"
        )
    print(f"control/maturity same-action rate: {report['cross_engine']['same_action_rate']:.1%}")

    if args.json_path:
        path = Path(args.json_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"JSON report: {path}")


if __name__ == "__main__":
    main()
