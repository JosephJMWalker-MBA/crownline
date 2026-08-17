from __future__ import annotations

import argparse
import json
from pathlib import Path

from crownline_benchmark import BaselineEngine, _source_fingerprint
from crownline_ordering_engines import ScoreOrderedBaselineEngine
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
    static_ordered = StaticOrderedBaselineEngine(f"static-ordered-d{depth}", depth=depth)
    score_ordered = ScoreOrderedBaselineEngine(f"score-ordered-d{depth}", depth=depth)
    records = []

    for scenario in position_suite():
        for game_number, fixture in ((1, scenario.game1), (2, scenario.game2)):
            state = _state_for_fixture(fixture)
            participant = state.participant_for_color(state.current_game.turn)

            baseline_decision = baseline.choose(state, participant)
            static_decision = static_ordered.choose(state, participant)
            score_decision = score_ordered.choose(state, participant)

            baseline_action = (baseline_decision.notation, baseline_decision.meld_line)
            static_action = (static_decision.notation, static_decision.meld_line)
            score_action = (score_decision.notation, score_decision.meld_line)
            if not (baseline_action == static_action == score_action):
                raise AssertionError(
                    f"Ordering action mismatch at {scenario.scenario_id} Game {game_number}: "
                    f"baseline={baseline_action}, static={static_action}, score={score_action}"
                )

            records.append(
                {
                    "scenario_id": scenario.scenario_id,
                    "game_number": game_number,
                    "fingerprint": fixture.fingerprint,
                    "baseline_nodes": baseline_decision.search_nodes,
                    "static_ordered_nodes": static_decision.search_nodes,
                    "score_ordered_nodes": score_decision.search_nodes,
                    "baseline_ms": baseline_decision.elapsed_ms,
                    "static_ordered_ms": static_decision.elapsed_ms,
                    "score_ordered_ms": score_decision.elapsed_ms,
                }
            )

    def total(field: str):
        return sum(record[field] for record in records)

    baseline_nodes = total("baseline_nodes")
    static_nodes = total("static_ordered_nodes")
    score_nodes = total("score_ordered_nodes")
    baseline_ms = total("baseline_ms")
    static_ms = total("static_ordered_ms")
    score_ms = total("score_ordered_ms")

    return {
        "depth": depth,
        "position_count": len(records),
        "action_equivalence": True,
        "baseline_nodes": baseline_nodes,
        "static_ordered_nodes": static_nodes,
        "score_ordered_nodes": score_nodes,
        "static_node_reduction_fraction": (
            1.0 - static_nodes / baseline_nodes if baseline_nodes else 0.0
        ),
        "score_node_reduction_fraction": (
            1.0 - score_nodes / baseline_nodes if baseline_nodes else 0.0
        ),
        "score_nodes_over_static_nodes": score_nodes / static_nodes if static_nodes else 0.0,
        "baseline_ms": baseline_ms,
        "static_ordered_ms": static_ms,
        "score_ordered_ms": score_ms,
        "static_over_baseline": static_ms / baseline_ms if baseline_ms else 0.0,
        "score_over_baseline": score_ms / baseline_ms if baseline_ms else 0.0,
        "score_over_static": score_ms / static_ms if static_ms else 0.0,
        "positions_score_reduces_nodes": sum(
            record["score_ordered_nodes"] < record["baseline_nodes"] for record in records
        ),
        "positions_score_increases_nodes": sum(
            record["score_ordered_nodes"] > record["baseline_nodes"] for record in records
        ),
        "records": records,
    }


def run(depths: tuple[int, ...]) -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "experiment": "score-only-move-ordering",
        "suite_id": POSITION_SUITE_ID,
        "rules_mode": "candidate",
        "position_count": 16,
        "hypothesis": (
            "Dropping the expensive mobility term from the move-ordering estimate "
            "retains most of static evaluator ordering's alpha-beta node reduction "
            "while materially reducing ordering overhead and preserving Baseline A actions."
        ),
        "depths": [_run_depth(depth) for depth in depths],
        "source_fingerprints": {
            "baseline_ai_sha256": _source_fingerprint("crownline_ai.py"),
            "static_search_engine_sha256": _source_fingerprint("crownline_search_engines.py"),
            "score_order_engine_sha256": _source_fingerprint("crownline_ordering_engines.py"),
            "position_suite_sha256": _source_fingerprint(
                str(POSITION_SUITE_PATH.relative_to(ROOT))
            ),
            "experiment_sha256": _source_fingerprint(
                "experiments/benchmark_score_only_ordering.py"
            ),
        },
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compare full-static and score-only alpha-beta move ordering."
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
    print("Crownline score-only move-ordering benchmark")
    print(f"Suite {report['suite_id']} | positions {report['position_count']}")
    for result in report["depths"]:
        print(
            f"d{result['depth']}: equivalent={result['action_equivalence']} | "
            f"baseline {result['baseline_nodes']} nodes | static {result['static_ordered_nodes']} | "
            f"score-only {result['score_ordered_nodes']} | "
            f"score latency {result['score_over_baseline']:.2f}x baseline / "
            f"{result['score_over_static']:.2f}x static"
        )
    if args.json_path:
        path = Path(args.json_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"JSON report: {path}")


if __name__ == "__main__":
    main()
