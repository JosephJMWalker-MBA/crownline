from __future__ import annotations

import argparse
import json
from pathlib import Path

from crownline_benchmark import BaselineEngine, _source_fingerprint
from crownline_combined_search import ScoreOrderedStructuralTTBaselineEngine
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
    ordered = ScoreOrderedBaselineEngine(f"score-ordered-d{depth}", depth=depth)
    combined = ScoreOrderedStructuralTTBaselineEngine(
        f"score-ordered-tt-d{depth}",
        depth=depth,
    )
    records = []

    for scenario in position_suite():
        for game_number, fixture in ((1, scenario.game1), (2, scenario.game2)):
            state = _state_for_fixture(fixture)
            participant = state.participant_for_color(state.current_game.turn)
            hits_before = combined.total_cache_hits

            baseline_decision = baseline.choose(state, participant)
            ordered_decision = ordered.choose(state, participant)
            combined_decision = combined.choose(state, participant)
            hits = combined.total_cache_hits - hits_before

            baseline_action = (baseline_decision.notation, baseline_decision.meld_line)
            ordered_action = (ordered_decision.notation, ordered_decision.meld_line)
            combined_action = (combined_decision.notation, combined_decision.meld_line)
            if not (baseline_action == ordered_action == combined_action):
                raise AssertionError(
                    f"Combined-search action mismatch at {scenario.scenario_id} Game {game_number}: "
                    f"baseline={baseline_action}, ordered={ordered_action}, combined={combined_action}"
                )

            records.append(
                {
                    "scenario_id": scenario.scenario_id,
                    "game_number": game_number,
                    "fingerprint": fixture.fingerprint,
                    "baseline_nodes": baseline_decision.search_nodes,
                    "ordered_nodes": ordered_decision.search_nodes,
                    "combined_expanded_nodes": combined_decision.search_nodes,
                    "combined_cache_hits": hits,
                    "baseline_ms": baseline_decision.elapsed_ms,
                    "ordered_ms": ordered_decision.elapsed_ms,
                    "combined_ms": combined_decision.elapsed_ms,
                }
            )

    def total(field: str):
        return sum(record[field] for record in records)

    baseline_nodes = total("baseline_nodes")
    ordered_nodes = total("ordered_nodes")
    combined_nodes = total("combined_expanded_nodes")
    cache_hits = total("combined_cache_hits")
    baseline_ms = total("baseline_ms")
    ordered_ms = total("ordered_ms")
    combined_ms = total("combined_ms")
    probes = combined_nodes + cache_hits

    return {
        "depth": depth,
        "position_count": len(records),
        "action_equivalence": True,
        "baseline_nodes": baseline_nodes,
        "score_ordered_nodes": ordered_nodes,
        "combined_expanded_nodes": combined_nodes,
        "combined_cache_hits": cache_hits,
        "combined_cache_hit_rate": cache_hits / probes if probes else 0.0,
        "ordering_node_reduction_vs_baseline": (
            1.0 - ordered_nodes / baseline_nodes if baseline_nodes else 0.0
        ),
        "incremental_tt_node_reduction_vs_ordered": (
            1.0 - combined_nodes / ordered_nodes if ordered_nodes else 0.0
        ),
        "combined_node_reduction_vs_baseline": (
            1.0 - combined_nodes / baseline_nodes if baseline_nodes else 0.0
        ),
        "baseline_ms": baseline_ms,
        "score_ordered_ms": ordered_ms,
        "combined_ms": combined_ms,
        "ordered_over_baseline": ordered_ms / baseline_ms if baseline_ms else 0.0,
        "combined_over_ordered": combined_ms / ordered_ms if ordered_ms else 0.0,
        "combined_over_baseline": combined_ms / baseline_ms if baseline_ms else 0.0,
        "positions_with_cache_hits": sum(
            record["combined_cache_hits"] > 0 for record in records
        ),
        "records": records,
    }


def run(depths: tuple[int, ...]) -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "experiment": "score-ordering-plus-structural-exact-tt",
        "suite_id": POSITION_SUITE_ID,
        "rules_mode": "candidate",
        "position_count": 16,
        "hypothesis": (
            "Adding the already-validated structural exact transposition table "
            "to score-only ordered search further reduces expanded nodes and may "
            "recover enough work to offset cache overhead, without changing any action."
        ),
        "depths": [_run_depth(depth) for depth in depths],
        "source_fingerprints": {
            "baseline_ai_sha256": _source_fingerprint("crownline_ai.py"),
            "score_order_engine_sha256": _source_fingerprint("crownline_ordering_engines.py"),
            "combined_engine_sha256": _source_fingerprint("crownline_combined_search.py"),
            "position_suite_sha256": _source_fingerprint(
                str(POSITION_SUITE_PATH.relative_to(ROOT))
            ),
            "experiment_sha256": _source_fingerprint(
                "experiments/benchmark_ordering_plus_tt.py"
            ),
        },
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Measure structural exact TT added to score-ordered search."
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
    print("Crownline score-order + structural-TT benchmark")
    print(f"Suite {report['suite_id']} | positions {report['position_count']}")
    for result in report["depths"]:
        print(
            f"d{result['depth']}: equivalent={result['action_equivalence']} | "
            f"nodes baseline {result['baseline_nodes']} / ordered {result['score_ordered_nodes']} / "
            f"combined {result['combined_expanded_nodes']} | hits {result['combined_cache_hits']} | "
            f"combined latency {result['combined_over_baseline']:.2f}x baseline / "
            f"{result['combined_over_ordered']:.2f}x ordered"
        )
    if args.json_path:
        path = Path(args.json_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"JSON report: {path}")


if __name__ == "__main__":
    main()
