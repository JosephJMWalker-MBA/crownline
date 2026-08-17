from __future__ import annotations

import argparse
import json
from pathlib import Path

from crownline_benchmark import BaselineEngine, _source_fingerprint
from crownline_carried_ordering import CarriedScoreOrderedBaselineEngine
from crownline_delta_ordering import DeltaScoreOrderedBaselineEngine
from crownline_position_suite import POSITION_SUITE_ID, POSITION_SUITE_PATH, position_suite
from crownline_set import CrownlineSet


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = 1


def _state_for_fixture(fixture) -> CrownlineSet:
    return CrownlineSet(
        first_game_white="A",
        current_game=fixture.game(),
        rules_mode="candidate",
    )


def _run_depth(depth: int) -> dict:
    baseline = BaselineEngine(f"baseline-d{depth}", depth=depth)
    delta = DeltaScoreOrderedBaselineEngine(f"delta-d{depth}", depth=depth)
    carried = CarriedScoreOrderedBaselineEngine(f"carried-d{depth}", depth=depth)
    records = []

    for scenario in position_suite():
        for game_number, fixture in ((1, scenario.game1), (2, scenario.game2)):
            state = _state_for_fixture(fixture)
            participant = state.participant_for_color(state.current_game.turn)

            baseline_decision = baseline.choose(state, participant)
            delta_decision = delta.choose(state, participant)
            carried_decision = carried.choose(state, participant)

            baseline_action = (baseline_decision.notation, baseline_decision.meld_line)
            delta_action = (delta_decision.notation, delta_decision.meld_line)
            carried_action = (carried_decision.notation, carried_decision.meld_line)
            if not (baseline_action == delta_action == carried_action):
                raise AssertionError(
                    f"Carried-ordering action mismatch at {scenario.scenario_id} Game {game_number}"
                )
            if delta_decision.search_nodes != carried_decision.search_nodes:
                raise AssertionError(
                    f"Carried ordering changed search tree at {scenario.scenario_id} Game {game_number}"
                )

            records.append(
                {
                    "scenario_id": scenario.scenario_id,
                    "game_number": game_number,
                    "fingerprint": fixture.fingerprint,
                    "baseline_nodes": baseline_decision.search_nodes,
                    "ordered_nodes": carried_decision.search_nodes,
                    "baseline_ms": baseline_decision.elapsed_ms,
                    "delta_ms": delta_decision.elapsed_ms,
                    "carried_ms": carried_decision.elapsed_ms,
                }
            )

    def total(field: str):
        return sum(record[field] for record in records)

    baseline_nodes = total("baseline_nodes")
    carried_nodes = total("ordered_nodes")
    baseline_ms = total("baseline_ms")
    delta_ms = total("delta_ms")
    carried_ms = total("carried_ms")

    return {
        "depth": depth,
        "position_count": len(records),
        "action_equivalence": True,
        "search_tree_equivalence_to_delta_ordering": True,
        "baseline_nodes": baseline_nodes,
        "carried_ordered_nodes": carried_nodes,
        "node_reduction_fraction_vs_baseline": (
            1.0 - carried_nodes / baseline_nodes if baseline_nodes else 0.0
        ),
        "baseline_ms": baseline_ms,
        "delta_ordered_ms": delta_ms,
        "carried_ordered_ms": carried_ms,
        "delta_over_baseline": delta_ms / baseline_ms if baseline_ms else 0.0,
        "carried_over_baseline": carried_ms / baseline_ms if baseline_ms else 0.0,
        "carried_over_delta": carried_ms / delta_ms if delta_ms else 0.0,
        "records": records,
    }


def run(depths: tuple[int, ...]) -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "experiment": "carried-score-ordering",
        "suite_id": POSITION_SUITE_ID,
        "rules_mode": "candidate",
        "position_count": 16,
        "hypothesis": (
            "Carrying exact W/B score totals recursively removes repeated parent "
            "score scans while preserving the identical delta-ordering search tree, "
            "reducing wall-clock overhead without changing any action."
        ),
        "depths": [_run_depth(depth) for depth in depths],
        "source_fingerprints": {
            "baseline_ai_sha256": _source_fingerprint("crownline_ai.py"),
            "delta_order_engine_sha256": _source_fingerprint("crownline_delta_ordering.py"),
            "carried_order_engine_sha256": _source_fingerprint("crownline_carried_ordering.py"),
            "position_suite_sha256": _source_fingerprint(
                str(POSITION_SUITE_PATH.relative_to(ROOT))
            ),
            "experiment_sha256": _source_fingerprint(
                "experiments/benchmark_carried_ordering.py"
            ),
        },
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Measure recursively carried score ordering.")
    parser.add_argument("--depths", type=int, nargs="+", default=(2, 3, 4), choices=range(1, 5))
    parser.add_argument("--json", dest="json_path", default=None)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    report = run(tuple(args.depths))
    print("Crownline carried-score move-ordering benchmark")
    print(f"Suite {report['suite_id']} | positions {report['position_count']}")
    for result in report["depths"]:
        print(
            f"d{result['depth']}: tree-equivalent={result['search_tree_equivalence_to_delta_ordering']} | "
            f"nodes {result['baseline_nodes']} -> {result['carried_ordered_nodes']} | "
            f"carried {result['carried_over_baseline']:.2f}x baseline / "
            f"{result['carried_over_delta']:.2f}x delta"
        )
    if args.json_path:
        path = Path(args.json_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"JSON report: {path}")


if __name__ == "__main__":
    main()
