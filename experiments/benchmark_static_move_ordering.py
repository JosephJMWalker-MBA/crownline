from __future__ import annotations

import argparse
import json
from pathlib import Path

from crownline_benchmark import BaselineEngine, _source_fingerprint
from crownline_position_suite import POSITION_SUITE_ID, POSITION_SUITE_PATH, position_suite
from crownline_search_engines import StaticOrderedBaselineEngine
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
    ordered = StaticOrderedBaselineEngine(f"static-ordered-d{depth}", depth=depth)
    records = []

    for scenario in position_suite():
        for game_number, fixture in ((1, scenario.game1), (2, scenario.game2)):
            state = _state_for_fixture(fixture)
            participant = state.participant_for_color(state.current_game.turn)
            before_order_evals = ordered.total_ordering_evaluations
            before_cutoffs = ordered.total_cutoff_nodes

            baseline_decision = baseline.choose(state, participant)
            ordered_decision = ordered.choose(state, participant)
            ordering_evaluations = ordered.total_ordering_evaluations - before_order_evals
            cutoff_nodes = ordered.total_cutoff_nodes - before_cutoffs

            baseline_action = (baseline_decision.notation, baseline_decision.meld_line)
            ordered_action = (ordered_decision.notation, ordered_decision.meld_line)
            if baseline_action != ordered_action:
                raise AssertionError(
                    f"Ordered action mismatch at {scenario.scenario_id} Game {game_number}: "
                    f"baseline={baseline_action}, ordered={ordered_action}"
                )

            records.append(
                {
                    "scenario_id": scenario.scenario_id,
                    "game_number": game_number,
                    "fingerprint": fixture.fingerprint,
                    "baseline_nodes": baseline_decision.search_nodes,
                    "ordered_nodes": ordered_decision.search_nodes,
                    "ordering_evaluations": ordering_evaluations,
                    "ordered_cutoff_nodes": cutoff_nodes,
                    "baseline_ms": baseline_decision.elapsed_ms,
                    "ordered_ms": ordered_decision.elapsed_ms,
                }
            )

    baseline_nodes = sum(record["baseline_nodes"] for record in records)
    ordered_nodes = sum(record["ordered_nodes"] for record in records)
    baseline_ms = sum(record["baseline_ms"] for record in records)
    ordered_ms = sum(record["ordered_ms"] for record in records)
    ordering_evaluations = sum(record["ordering_evaluations"] for record in records)

    return {
        "depth": depth,
        "position_count": len(records),
        "action_equivalence": True,
        "baseline_nodes": baseline_nodes,
        "ordered_nodes": ordered_nodes,
        "expanded_node_reduction_fraction": (
            1.0 - ordered_nodes / baseline_nodes if baseline_nodes else 0.0
        ),
        "ordering_evaluations": ordering_evaluations,
        "baseline_ms": baseline_ms,
        "ordered_ms": ordered_ms,
        "latency_ratio_ordered_over_baseline": (
            ordered_ms / baseline_ms if baseline_ms else 0.0
        ),
        "positions_with_node_reduction": sum(
            record["ordered_nodes"] < record["baseline_nodes"] for record in records
        ),
        "positions_with_node_increase": sum(
            record["ordered_nodes"] > record["baseline_nodes"] for record in records
        ),
        "records": records,
    }


def run(depths: tuple[int, ...]) -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "experiment": "static-evaluator-move-ordering",
        "suite_id": POSITION_SUITE_ID,
        "rules_mode": "candidate",
        "position_count": 16,
        "hypothesis": (
            "Ordering internal alpha-beta children by the unchanged static "
            "Baseline A evaluator reduces expanded search nodes and wall-clock "
            "time without changing any chosen action."
        ),
        "ordering_policy": (
            "At maximizing nodes search the highest one-ply static evaluation "
            "first; at minimizing nodes search the lowest first. Root action "
            "order and lexicographic tie-breaking remain unchanged."
        ),
        "depths": [_run_depth(depth) for depth in depths],
        "source_fingerprints": {
            "baseline_ai_sha256": _source_fingerprint("crownline_ai.py"),
            "search_engine_sha256": _source_fingerprint("crownline_search_engines.py"),
            "position_suite_sha256": _source_fingerprint(
                str(POSITION_SUITE_PATH.relative_to(ROOT))
            ),
            "experiment_sha256": _source_fingerprint(
                "experiments/benchmark_static_move_ordering.py"
            ),
        },
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Measure static-evaluator alpha-beta move ordering."
    )
    parser.add_argument(
        "--depths",
        type=int,
        nargs="+",
        default=(2, 3, 4),
        choices=range(1, 5),
    )
    parser.add_argument("--json", dest="json_path", default=None)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    report = run(tuple(args.depths))
    print("Crownline static move-ordering benchmark")
    print(f"Suite {report['suite_id']} | positions {report['position_count']}")
    for result in report["depths"]:
        print(
            f"d{result['depth']}: equivalent={result['action_equivalence']} | "
            f"nodes {result['baseline_nodes']} -> {result['ordered_nodes']} "
            f"({result['expanded_node_reduction_fraction']:.1%} reduction) | "
            f"ordering evals {result['ordering_evaluations']} | "
            f"latency {result['latency_ratio_ordered_over_baseline']:.2f}x baseline"
        )
    if args.json_path:
        path = Path(args.json_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"JSON report: {path}")


if __name__ == "__main__":
    main()
