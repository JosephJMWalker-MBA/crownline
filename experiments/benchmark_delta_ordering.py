from __future__ import annotations

import argparse
import json
from pathlib import Path

from crownline_benchmark import BaselineEngine, _source_fingerprint
from crownline_delta_ordering import DeltaScoreOrderedBaselineEngine
from crownline_ordering_engines import ScoreOrderedBaselineEngine
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
    score_ordered = ScoreOrderedBaselineEngine(f"score-ordered-d{depth}", depth=depth)
    delta_ordered = DeltaScoreOrderedBaselineEngine(f"delta-ordered-d{depth}", depth=depth)
    records = []

    for scenario in position_suite():
        for game_number, fixture in ((1, scenario.game1), (2, scenario.game2)):
            state = _state_for_fixture(fixture)
            participant = state.participant_for_color(state.current_game.turn)

            baseline_decision = baseline.choose(state, participant)
            score_decision = score_ordered.choose(state, participant)
            delta_decision = delta_ordered.choose(state, participant)

            baseline_action = (baseline_decision.notation, baseline_decision.meld_line)
            score_action = (score_decision.notation, score_decision.meld_line)
            delta_action = (delta_decision.notation, delta_decision.meld_line)
            if not (baseline_action == score_action == delta_action):
                raise AssertionError(
                    f"Delta-ordering action mismatch at {scenario.scenario_id} Game {game_number}: "
                    f"baseline={baseline_action}, score={score_action}, delta={delta_action}"
                )
            if score_decision.search_nodes != delta_decision.search_nodes:
                raise AssertionError(
                    f"Delta ordering changed the search tree at {scenario.scenario_id} "
                    f"Game {game_number}: score={score_decision.search_nodes}, "
                    f"delta={delta_decision.search_nodes}"
                )

            records.append(
                {
                    "scenario_id": scenario.scenario_id,
                    "game_number": game_number,
                    "fingerprint": fixture.fingerprint,
                    "baseline_nodes": baseline_decision.search_nodes,
                    "score_ordered_nodes": score_decision.search_nodes,
                    "delta_ordered_nodes": delta_decision.search_nodes,
                    "baseline_ms": baseline_decision.elapsed_ms,
                    "score_ordered_ms": score_decision.elapsed_ms,
                    "delta_ordered_ms": delta_decision.elapsed_ms,
                }
            )

    def total(field: str):
        return sum(record[field] for record in records)

    baseline_nodes = total("baseline_nodes")
    score_nodes = total("score_ordered_nodes")
    delta_nodes = total("delta_ordered_nodes")
    baseline_ms = total("baseline_ms")
    score_ms = total("score_ordered_ms")
    delta_ms = total("delta_ordered_ms")

    return {
        "depth": depth,
        "position_count": len(records),
        "action_equivalence": True,
        "search_tree_equivalence_to_score_ordering": score_nodes == delta_nodes,
        "baseline_nodes": baseline_nodes,
        "score_ordered_nodes": score_nodes,
        "delta_ordered_nodes": delta_nodes,
        "node_reduction_fraction_vs_baseline": (
            1.0 - delta_nodes / baseline_nodes if baseline_nodes else 0.0
        ),
        "baseline_ms": baseline_ms,
        "score_ordered_ms": score_ms,
        "delta_ordered_ms": delta_ms,
        "score_over_baseline": score_ms / baseline_ms if baseline_ms else 0.0,
        "delta_over_baseline": delta_ms / baseline_ms if baseline_ms else 0.0,
        "delta_over_score_ordering": delta_ms / score_ms if score_ms else 0.0,
        "records": records,
    }


def run(depths: tuple[int, ...]) -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "experiment": "delta-equivalent-score-ordering",
        "suite_id": POSITION_SUITE_ID,
        "rules_mode": "candidate",
        "position_count": 16,
        "hypothesis": (
            "Computing the existing score-only sibling ordering estimate from one "
            "parent score scan plus exact move deltas preserves the identical search "
            "tree while reducing ordering overhead enough to improve wall-clock time."
        ),
        "depths": [_run_depth(depth) for depth in depths],
        "source_fingerprints": {
            "baseline_ai_sha256": _source_fingerprint("crownline_ai.py"),
            "score_order_engine_sha256": _source_fingerprint("crownline_ordering_engines.py"),
            "delta_order_engine_sha256": _source_fingerprint("crownline_delta_ordering.py"),
            "position_suite_sha256": _source_fingerprint(
                str(POSITION_SUITE_PATH.relative_to(ROOT))
            ),
            "experiment_sha256": _source_fingerprint(
                "experiments/benchmark_delta_ordering.py"
            ),
        },
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Measure delta-equivalent score-only alpha-beta ordering."
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
    print("Crownline delta-equivalent move-ordering benchmark")
    print(f"Suite {report['suite_id']} | positions {report['position_count']}")
    for result in report["depths"]:
        print(
            f"d{result['depth']}: tree-equivalent={result['search_tree_equivalence_to_score_ordering']} | "
            f"nodes {result['baseline_nodes']} -> {result['delta_ordered_nodes']} | "
            f"delta latency {result['delta_over_baseline']:.2f}x baseline / "
            f"{result['delta_over_score_ordering']:.2f}x score-order"
        )
    if args.json_path:
        path = Path(args.json_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"JSON report: {path}")


if __name__ == "__main__":
    main()
