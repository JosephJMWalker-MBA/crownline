from __future__ import annotations

import argparse
import json
from pathlib import Path

from crownline_benchmark import _source_fingerprint
from crownline_king_position_suite import KING_POSITION_SUITE_PATH, king_position_suite
from experiments.benchmark_time_budget_stability import _engine_summary, _one, _state


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = 1


def run(*, repeats: int, budget_ms: float, max_depth: int, maturity_weight: float) -> dict:
    if repeats < 2:
        raise ValueError("repeats must be at least 2")

    control_rows: list[dict] = []
    maturity_rows: list[dict] = []
    same_rep_pairs = []
    fixtures = list(king_position_suite())

    for fixture in fixtures:
        state = _state(fixture)
        participant = state.participant_for_color(state.current_game.turn)
        for repeat in range(repeats):
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
                    "fixture_id": fixture.fixture_id,
                    "repeat": repeat + 1,
                    "order_index": order.index(engine),
                    **result,
                }
                results[engine] = result
                (control_rows if engine == "control" else maturity_rows).append(row)
            same_rep_pairs.append(
                {
                    "fixture_id": fixture.fixture_id,
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
    changed_fixtures = sorted(
        {
            item["fixture_id"]
            for item in same_rep_pairs
            if not item["same_action"]
        }
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "experiment": "stage3-150ms-king-hard-case-wall-clock-stability-audit",
        "rules_mode": "candidate",
        "repeats": repeats,
        "budget_ms": budget_ms,
        "max_depth": max_depth,
        "maturity_weight": maturity_weight,
        "position_count": len(fixtures),
        "hypothesis": (
            "The King hard-case suite is where promotion maturity can actually affect policy. "
            "Repeated 150 ms decisions should distinguish a stable strategic policy difference "
            "from a deadline-boundary artifact before maturity is composed with repetition memory."
        ),
        "control": control,
        "maturity": maturity,
        "cross_engine": {
            "same_rep_decisions": len(same_rep_pairs),
            "same_action_count": sum(item["same_action"] for item in same_rep_pairs),
            "same_action_rate": sum(item["same_action"] for item in same_rep_pairs) / len(same_rep_pairs),
            "fixtures_with_policy_difference": changed_fixtures,
            "pairs": same_rep_pairs,
        },
        "source_fingerprints": {
            "king_position_suite_sha256": _source_fingerprint(str(KING_POSITION_SUITE_PATH.relative_to(ROOT))),
            "base_stability_audit_sha256": _source_fingerprint("experiments/benchmark_time_budget_stability.py"),
            "experiment_sha256": _source_fingerprint("experiments/benchmark_time_budget_king_stability.py"),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit 150 ms Crownline policy stability on King hard cases.")
    parser.add_argument("--repeats", type=int, default=8)
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
    print("Crownline King hard-case 150 ms stability audit")
    for name in ("control", "maturity"):
        s = report[name]
        print(
            f"{name}: action-variant positions {s['positions_with_action_variation']}/{s['positions']} | "
            f"depth-variant positions {s['positions_with_depth_variation']}/{s['positions']} | "
            f"mean depth {s['mean_completed_depth']:.3f} | full-depth {s['full_depth_rate']:.1%}"
        )
    cross = report["cross_engine"]
    print(
        f"same-action rate {cross['same_action_rate']:.1%} | policy-difference fixtures "
        f"{cross['fixtures_with_policy_difference']}"
    )

    if args.json_path:
        path = Path(args.json_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"JSON report: {path}")


if __name__ == "__main__":
    main()
