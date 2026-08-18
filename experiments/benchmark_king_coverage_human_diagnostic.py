from __future__ import annotations

import argparse
import json
from pathlib import Path
from statistics import mean, median
from typing import Any, Optional

from crownline_human_decision_suite import HUMAN_SUITE_ID, human_decision_suite
from crownline_king_coverage_experiment import rank_king_coverage_actions
from crownline_rules import Line


SCHEMA_VERSION = 1


def _key(notation: str, line: Optional[Line]) -> tuple[str, str]:
    return notation, "-".join(line) if line else ""


def _weight_report(weight: float, *, depth: int, maturity_weight: float) -> dict[str, Any]:
    fixtures = human_decision_suite()
    records = []
    for fixture in fixtures:
        ranked = rank_king_coverage_actions(
            fixture.state(),
            fixture.participant,
            depth=depth,
            maturity_weight=maturity_weight,
            coverage_weight=weight,
        )
        observed_key = _key(
            fixture.observed_action.notation,
            fixture.observed_action.meld_line,
        )
        observed_rank = next(
            index
            for index, (_, notation, _, meld_line) in enumerate(ranked, start=1)
            if _key(notation, meld_line) == observed_key
        )
        records.append(
            {
                "fixture_id": fixture.fixture_id,
                "bucket": fixture.bucket,
                "observed_rank": observed_rank,
                "root_action_count": len(ranked),
                "ai_best": {
                    "notation": ranked[0][1],
                    "meld_line": list(ranked[0][3]) if ranked[0][3] else None,
                    "value": ranked[0][0],
                },
                "observed_matches_ai_best": observed_rank == 1,
            }
        )

    buckets: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        buckets.setdefault(record["bucket"], []).append(record)

    bucket_summary = {}
    for bucket, items in buckets.items():
        ranks = [item["observed_rank"] for item in items]
        bucket_summary[bucket] = {
            "fixture_count": len(items),
            "ai_best_matches": sum(item["observed_matches_ai_best"] for item in items),
            "top3": sum(item["observed_rank"] <= 3 for item in items),
            "mean_rank": mean(ranks),
            "median_rank": median(ranks),
        }

    positive = [
        item
        for item in records
        if item["bucket"] in (
            "bot-crownline-construction",
            "human-royal-sweep-preparation",
        )
    ]
    positive_ranks = [item["observed_rank"] for item in positive]
    tactical = [item for item in records if item["bucket"] == "human-tactical-error"]
    return {
        "coverage_weight": weight,
        "summary": {
            "buckets": bucket_summary,
            "strategic_positive": {
                "fixture_count": len(positive),
                "ai_best_matches": sum(item["observed_matches_ai_best"] for item in positive),
                "top3": sum(item["observed_rank"] <= 3 for item in positive),
                "mean_rank": mean(positive_ranks),
                "median_rank": median(positive_ranks),
            },
            "tactical_error": {
                "fixture_count": len(tactical),
                "ai_best_matches": sum(item["observed_matches_ai_best"] for item in tactical),
                "top3": sum(item["observed_rank"] <= 3 for item in tactical),
                "mean_rank": mean(item["observed_rank"] for item in tactical),
                "median_rank": median(item["observed_rank"] for item in tactical),
            },
        },
        "fixtures": records,
    }


def run(
    *,
    weights: list[float],
    depth: int = 3,
    maturity_weight: float = 10.0,
) -> dict[str, Any]:
    if not weights:
        raise ValueError("At least one coverage weight is required")
    if any(weight < 0 for weight in weights):
        raise ValueError("Coverage weights must be non-negative")

    reports = [
        _weight_report(
            weight,
            depth=depth,
            maturity_weight=maturity_weight,
        )
        for weight in weights
    ]
    baseline = reports[0]
    if baseline["coverage_weight"] != 0:
        raise ValueError("The first weight must be zero to establish the control")

    baseline_best = {
        item["fixture_id"]: (
            item["ai_best"]["notation"],
            tuple(item["ai_best"]["meld_line"] or []),
        )
        for item in baseline["fixtures"]
    }
    for report in reports:
        changed = []
        for item in report["fixtures"]:
            current = (
                item["ai_best"]["notation"],
                tuple(item["ai_best"]["meld_line"] or []),
            )
            if current != baseline_best[item["fixture_id"]]:
                changed.append(item["fixture_id"])
        report["summary"]["root_action_changes_vs_w0"] = len(changed)
        report["summary"]["changed_fixture_ids_vs_w0"] = changed

    return {
        "schema_version": SCHEMA_VERSION,
        "experiment": "king-unretired-line-coverage-human-diagnostic",
        "suite_id": HUMAN_SUITE_ID,
        "rules_mode": "candidate",
        "depth": depth,
        "maturity_weight": maturity_weight,
        "hypothesis": (
            "Strategically successful Crownline-construction moves preserve or create more "
            "King memberships across still-unretired Crownline geometries than the current "
            "evaluator's preferred move. A small nonterminal weight on that exact coverage "
            "margin may move search toward successful construction trajectories without "
            "bundling threat, cooldown, capture-safety, or reachability features."
        ),
        "weights": weights,
        "reports": reports,
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sweep King unretired-line coverage weights.")
    parser.add_argument("--weights", type=float, nargs="+", default=[0, 5, 10, 20, 40, 80])
    parser.add_argument("--depth", type=int, default=3, choices=range(1, 5))
    parser.add_argument("--maturity-weight", type=float, default=10.0)
    parser.add_argument("--json", dest="json_path", default=None)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    report = run(
        weights=args.weights,
        depth=args.depth,
        maturity_weight=args.maturity_weight,
    )
    print("Crownline King-coverage human diagnostic")
    print(f"suite={report['suite_id']} depth={report['depth']} maturity={report['maturity_weight']:g}")
    for item in report["reports"]:
        strategic = item["summary"]["strategic_positive"]
        tactical = item["summary"]["tactical_error"]
        print(
            f"w={item['coverage_weight']:g}: strategic best={strategic['ai_best_matches']}/"
            f"{strategic['fixture_count']} top3={strategic['top3']} mean_rank={strategic['mean_rank']:.2f} | "
            f"tactical-error best={tactical['ai_best_matches']}/{tactical['fixture_count']} "
            f"mean_rank={tactical['mean_rank']:.2f} | root changes={item['summary']['root_action_changes_vs_w0']}"
        )

    if args.json_path:
        destination = Path(args.json_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"JSON report: {destination}")


if __name__ == "__main__":
    main()
