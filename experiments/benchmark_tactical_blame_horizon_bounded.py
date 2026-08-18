from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from experiments.benchmark_tactical_blame_horizon import WINDOW_PATH, _analyze_anchor


SCHEMA_VERSION = 1


def run(*, min_legs: int = 2, max_horizon_after_root: int = 4) -> dict[str, Any]:
    payload = json.loads(WINDOW_PATH.read_text(encoding="utf-8"))
    if payload.get("schema") != "crownline.tactical-blame-windows":
        raise ValueError("Unexpected tactical blame window schema")
    if min_legs < 2:
        raise ValueError("min_legs must be at least 2")
    if max_horizon_after_root < 0:
        raise ValueError("max_horizon_after_root must be non-negative")

    windows = []
    classifications: dict[str, int] = {}
    for window in payload["windows"]:
        eligible = [
            anchor
            for anchor in window["anchors"]
            if max(0, int(anchor["plies_to_punishment"]) - 1) <= max_horizon_after_root
        ]
        anchors = [
            _analyze_anchor(window, anchor, min_legs=min_legs)
            for anchor in eligible
        ]
        candidates = [anchor for anchor in anchors if anchor["blame_candidate"]]
        earliest = candidates[0] if candidates else None
        oldest_window_anchor = window["anchors"][0]
        oldest_eligible = eligible[0] if eligible else None

        if earliest is None:
            classification = "no-avoidable-blame-point-in-bounded-window"
        elif earliest["move_index"] == window["target_move_index"]:
            classification = "immediate-move-blame"
        else:
            classification = "upstream-blame"
        classifications[classification] = classifications.get(classification, 0) + 1

        windows.append(
            {
                "fixture_id": window["fixture_id"],
                "target_move_index": window["target_move_index"],
                "punishment": window["punishment"],
                "classification": classification,
                "earliest_blame_move_index": earliest["move_index"] if earliest else None,
                "earliest_blame_plies_before_punishment": (
                    earliest["plies_to_observed_punishment"] if earliest else None
                ),
                "oldest_frozen_move_index": oldest_window_anchor["move_index"],
                "oldest_analyzed_move_index": oldest_eligible["move_index"] if oldest_eligible else None,
                "anchors": anchors,
            }
        )

    return {
        "schema_version": SCHEMA_VERSION,
        "experiment": "human-tactical-blame-horizon-bounded",
        "suite_id": payload["suite_id"],
        "rules_mode": "candidate",
        "min_capture_legs": min_legs,
        "max_horizon_after_root": max_horizon_after_root,
        "methodology": {
            "purpose": "locate an earlier avoidable decision without exploding the full game tree",
            "analyzed_anchors": "only frozen human decisions whose observed punishment is within the configured post-root horizon",
            "protected_policy": "choose any legal continuation that avoids a compound capture",
            "opponent_policy": "choose any legal continuation that forces a compound capture",
            "interpretation": "bounded tactical safety diagnosis, not proof of optimal play or causal uniqueness",
        },
        "summary": {
            "window_count": len(windows),
            "classifications": classifications,
            "blame_found": sum(
                item["classification"] != "no-avoidable-blame-point-in-bounded-window"
                for item in windows
            ),
        },
        "windows": windows,
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run bounded Crownline tactical blame analysis.")
    parser.add_argument("--min-legs", type=int, default=2)
    parser.add_argument("--max-horizon-after-root", type=int, default=4)
    parser.add_argument("--json", dest="json_path", default=None)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    report = run(
        min_legs=args.min_legs,
        max_horizon_after_root=args.max_horizon_after_root,
    )
    print("Crownline bounded tactical blame diagnostic")
    print(
        f"suite={report['suite_id']} horizon={report['max_horizon_after_root']} "
        f"classifications={report['summary']['classifications']}"
    )
    for window in report["windows"]:
        print(
            f"{window['fixture_id']}: {window['classification']} | "
            f"earliest={window['earliest_blame_move_index']} | "
            f"oldest_analyzed={window['oldest_analyzed_move_index']}"
        )

    if args.json_path:
        destination = Path(args.json_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"JSON report: {destination}")


if __name__ == "__main__":
    main()
