from __future__ import annotations

import argparse
import json
from pathlib import Path
from statistics import mean, median
from typing import Any, Optional

from crownline_human_decision_suite import human_decision_suite
from crownline_mandatory_capture_quiescence_experiment import rank_quiescence_actions
from crownline_rules import Line
from crownline_set import CrownlineSet
from crownline_state_notation import parse_clsn


ROOT = Path(__file__).resolve().parents[1]
BLAME_WINDOWS_PATH = ROOT / "benchmarks" / "human_tactical_blame_windows_v0_1.json"
BLAME_REPORT_PATH = ROOT / "benchmarks" / "tactical_blame_horizon_bounded_v0_1.json"
SCHEMA_VERSION = 1


def _key(notation: str, line: Optional[Line]) -> tuple[str, str]:
    return notation, "-".join(line) if line else ""


def _blame_fixtures() -> list[dict[str, Any]]:
    windows_payload = json.loads(BLAME_WINDOWS_PATH.read_text(encoding="utf-8"))
    report_payload = json.loads(BLAME_REPORT_PATH.read_text(encoding="utf-8"))
    windows = {item["fixture_id"]: item for item in windows_payload["windows"]}
    result = []
    for diagnosis in report_payload["windows"]:
        move_index = diagnosis["earliest_blame_move_index"]
        if move_index is None:
            continue
        window = windows[diagnosis["fixture_id"]]
        anchor = next(item for item in window["anchors"] if item["move_index"] == move_index)
        result.append(
            {
                "fixture_id": diagnosis["fixture_id"],
                "bucket": "human-tactical-blame-point",
                "first_game_white": window["first_game_white"],
                "participant": window["participant"],
                "clsn": anchor["clsn"],
                "observed_action": anchor["observed_action"],
                "punishment": window["punishment"],
                "classification": diagnosis["classification"],
                "plies_before_punishment": diagnosis["earliest_blame_plies_before_punishment"],
            }
        )
    return result


def _strategic_fixtures() -> list[dict[str, Any]]:
    result = []
    for fixture in human_decision_suite():
        if fixture.bucket not in (
            "bot-crownline-construction",
            "human-royal-sweep-preparation",
        ):
            continue
        result.append(
            {
                "fixture_id": fixture.fixture_id,
                "bucket": fixture.bucket,
                "first_game_white": fixture.first_game_white,
                "participant": fixture.participant,
                "clsn": fixture.clsn,
                "observed_action": {
                    "notation": fixture.observed_action.notation,
                    "meld_line": list(fixture.observed_action.meld_line)
                    if fixture.observed_action.meld_line
                    else None,
                },
            }
        )
    return result


def _state(item: dict[str, Any]) -> CrownlineSet:
    return CrownlineSet(
        first_game_white=item["first_game_white"],
        current_game=parse_clsn(item["clsn"]),
        rules_mode="candidate",
    )


def _rank_observed(item: dict[str, Any], *, depth: int, maturity_weight: float, qdepth: int) -> dict[str, Any]:
    state = _state(item)
    ranked = rank_quiescence_actions(
        state,
        item["participant"],
        depth=depth,
        maturity_weight=maturity_weight,
        qdepth=qdepth,
    )
    observed_line = tuple(item["observed_action"]["meld_line"]) if item["observed_action"].get("meld_line") else None
    observed_key = _key(item["observed_action"]["notation"], observed_line)
    rank = next(
        index
        for index, (_, notation, _, meld_line) in enumerate(ranked, start=1)
        if _key(notation, meld_line) == observed_key
    )
    return {
        "fixture_id": item["fixture_id"],
        "bucket": item["bucket"],
        "observed_rank": rank,
        "observed_matches_ai_best": rank == 1,
        "root_action_count": len(ranked),
        "ai_best": {
            "notation": ranked[0][1],
            "meld_line": list(ranked[0][3]) if ranked[0][3] else None,
            "value": ranked[0][0],
        },
        "observed": {
            "notation": item["observed_action"]["notation"],
            "meld_line": item["observed_action"].get("meld_line"),
        },
        "context": {
            key: item[key]
            for key in ("classification", "plies_before_punishment", "punishment")
            if key in item
        },
    }


def _summary(items: list[dict[str, Any]]) -> dict[str, Any]:
    ranks = [item["observed_rank"] for item in items]
    return {
        "fixture_count": len(items),
        "ai_best_matches": sum(item["observed_matches_ai_best"] for item in items),
        "top3": sum(item["observed_rank"] <= 3 for item in items),
        "mean_rank": mean(ranks),
        "median_rank": median(ranks),
    }


def _report(qdepth: int, *, depth: int, maturity_weight: float) -> dict[str, Any]:
    fixtures = _blame_fixtures() + _strategic_fixtures()
    records = [
        _rank_observed(
            fixture,
            depth=depth,
            maturity_weight=maturity_weight,
            qdepth=qdepth,
        )
        for fixture in fixtures
    ]
    buckets: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        buckets.setdefault(record["bucket"], []).append(record)
    strategic = [
        record
        for record in records
        if record["bucket"] in (
            "bot-crownline-construction",
            "human-royal-sweep-preparation",
        )
    ]
    return {
        "qdepth": qdepth,
        "summary": {
            "buckets": {bucket: _summary(items) for bucket, items in buckets.items()},
            "strategic_positive": _summary(strategic),
            "tactical_blame": _summary(buckets["human-tactical-blame-point"]),
        },
        "fixtures": records,
    }


def run(*, qdepths: list[int], depth: int = 3, maturity_weight: float = 10.0) -> dict[str, Any]:
    if not qdepths or qdepths[0] != 0:
        raise ValueError("qdepths must begin with zero to establish the exact control")
    if any(value < 0 for value in qdepths):
        raise ValueError("qdepth values must be non-negative")

    reports = [
        _report(qdepth, depth=depth, maturity_weight=maturity_weight)
        for qdepth in qdepths
    ]
    baseline_best = {
        item["fixture_id"]: (
            item["ai_best"]["notation"],
            tuple(item["ai_best"]["meld_line"] or []),
        )
        for item in reports[0]["fixtures"]
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
        report["summary"]["root_action_changes_vs_q0"] = len(changed)
        report["summary"]["changed_fixture_ids_vs_q0"] = changed

    return {
        "schema_version": SCHEMA_VERSION,
        "experiment": "mandatory-capture-quiescence-human-diagnostic",
        "rules_mode": "candidate",
        "depth": depth,
        "maturity_weight": maturity_weight,
        "qdepths": qdepths,
        "hypothesis": (
            "The blame-horizon study found four human double-jump mistakes one decision earlier, "
            "exactly where depth-3 search can stop on an unstable position immediately before a "
            "forced opponent capture. Extending only leaf positions whose entire legal turn is "
            "capture-forced may reduce horizon-error preference without adding a new positional "
            "weight or treating Sovereign optional captures as mandatory."
        ),
        "reports": reports,
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sweep mandatory-capture quiescence depth on human diagnostics.")
    parser.add_argument("--qdepths", type=int, nargs="+", default=[0, 1, 2, 4])
    parser.add_argument("--depth", type=int, default=3, choices=range(1, 5))
    parser.add_argument("--maturity-weight", type=float, default=10.0)
    parser.add_argument("--json", dest="json_path", default=None)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    report = run(qdepths=args.qdepths, depth=args.depth, maturity_weight=args.maturity_weight)
    print("Crownline mandatory-capture quiescence human diagnostic")
    for item in report["reports"]:
        tactical = item["summary"]["tactical_blame"]
        strategic = item["summary"]["strategic_positive"]
        print(
            f"q={item['qdepth']}: bad-move best={tactical['ai_best_matches']}/{tactical['fixture_count']} "
            f"mean-rank={tactical['mean_rank']:.2f} | strategic best={strategic['ai_best_matches']}/"
            f"{strategic['fixture_count']} top3={strategic['top3']} mean-rank={strategic['mean_rank']:.2f} | "
            f"root changes={item['summary']['root_action_changes_vs_q0']}"
        )

    if args.json_path:
        path = Path(args.json_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"JSON report: {path}")


if __name__ == "__main__":
    main()
