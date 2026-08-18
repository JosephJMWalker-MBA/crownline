from __future__ import annotations

import argparse
import json
from pathlib import Path
from statistics import mean
from typing import Any

from experiments.benchmark_mandatory_capture_quiescence_human import _blame_fixtures, _rank_observed


SCHEMA_VERSION = 1


def run(*, qdepths: list[int], depth: int = 3, maturity_weight: float = 10.0) -> dict[str, Any]:
    if not qdepths or qdepths[0] != 0:
        raise ValueError("qdepths must begin with zero")
    fixtures = _blame_fixtures()
    reports = []
    baseline_best = None
    for qdepth in qdepths:
        records = [
            _rank_observed(
                fixture,
                depth=depth,
                maturity_weight=maturity_weight,
                qdepth=qdepth,
            )
            for fixture in fixtures
        ]
        current_best = {
            item["fixture_id"]: (
                item["ai_best"]["notation"],
                tuple(item["ai_best"]["meld_line"] or []),
            )
            for item in records
        }
        if baseline_best is None:
            baseline_best = current_best
        changed = [
            fixture_id
            for fixture_id, action in current_best.items()
            if action != baseline_best[fixture_id]
        ]
        reports.append(
            {
                "qdepth": qdepth,
                "summary": {
                    "fixture_count": len(records),
                    "bad_move_ai_best_matches": sum(item["observed_matches_ai_best"] for item in records),
                    "bad_move_top3": sum(item["observed_rank"] <= 3 for item in records),
                    "mean_bad_move_rank": mean(item["observed_rank"] for item in records),
                    "root_action_changes_vs_q0": len(changed),
                    "changed_fixture_ids_vs_q0": changed,
                },
                "fixtures": records,
            }
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "experiment": "mandatory-capture-quiescence-blame-points-only",
        "rules_mode": "candidate",
        "depth": depth,
        "maturity_weight": maturity_weight,
        "qdepths": qdepths,
        "reports": reports,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--qdepths", type=int, nargs="+", default=[0, 1])
    parser.add_argument("--depth", type=int, default=3)
    parser.add_argument("--maturity-weight", type=float, default=10.0)
    parser.add_argument("--json", dest="json_path")
    args = parser.parse_args()
    report = run(qdepths=args.qdepths, depth=args.depth, maturity_weight=args.maturity_weight)
    for item in report["reports"]:
        print(
            f"q={item['qdepth']}: bad-best={item['summary']['bad_move_ai_best_matches']}/"
            f"{item['summary']['fixture_count']} mean-rank={item['summary']['mean_bad_move_rank']:.2f} "
            f"changes={item['summary']['root_action_changes_vs_q0']}"
        )
    if args.json_path:
        path = Path(args.json_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"JSON report: {path}")


if __name__ == "__main__":
    main()
