from __future__ import annotations

import argparse
import json
from pathlib import Path

from crownline_benchmark import BaselineEngine, _source_fingerprint
from crownline_combined_search import ScoreOrderedStructuralTTBaselineEngine
from crownline_delta_tt import DeltaScoreOrderedStructuralTTBaselineEngine
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
    score_tt = ScoreOrderedStructuralTTBaselineEngine(f"score-tt-d{depth}", depth=depth)
    delta_tt = DeltaScoreOrderedStructuralTTBaselineEngine(f"delta-tt-d{depth}", depth=depth)
    records = []

    for scenario in position_suite():
        for game_number, fixture in ((1, scenario.game1), (2, scenario.game2)):
            state = _state_for_fixture(fixture)
            participant = state.participant_for_color(state.current_game.turn)
            score_hits_before = score_tt.total_cache_hits
            delta_hits_before = delta_tt.total_cache_hits

            baseline_decision = baseline.choose(state, participant)
            score_decision = score_tt.choose(state, participant)
            delta_decision = delta_tt.choose(state, participant)
            score_hits = score_tt.total_cache_hits - score_hits_before
            delta_hits = delta_tt.total_cache_hits - delta_hits_before

            baseline_action = (baseline_decision.notation, baseline_decision.meld_line)
            score_action = (score_decision.notation, score_decision.meld_line)
            delta_action = (delta_decision.notation, delta_decision.meld_line)
            if not (baseline_action == score_action == delta_action):
                raise AssertionError(
                    f"Delta-TT action mismatch at {scenario.scenario_id} Game {game_number}"
                )
            if score_decision.search_nodes != delta_decision.search_nodes:
                raise AssertionError(
                    f"Delta-TT changed expanded nodes at {scenario.scenario_id} Game {game_number}"
                )
            if score_hits != delta_hits:
                raise AssertionError(
                    f"Delta-TT changed cache hits at {scenario.scenario_id} Game {game_number}"
                )

            records.append(
                {
                    "scenario_id": scenario.scenario_id,
                    "game_number": game_number,
                    "fingerprint": fixture.fingerprint,
                    "baseline_nodes": baseline_decision.search_nodes,
                    "combined_nodes": delta_decision.search_nodes,
                    "cache_hits": delta_hits,
                    "baseline_ms": baseline_decision.elapsed_ms,
                    "score_tt_ms": score_decision.elapsed_ms,
                    "delta_tt_ms": delta_decision.elapsed_ms,
                }
            )

    def total(field: str):
        return sum(record[field] for record in records)

    baseline_nodes = total("baseline_nodes")
    combined_nodes = total("combined_nodes")
    cache_hits = total("cache_hits")
    baseline_ms = total("baseline_ms")
    score_tt_ms = total("score_tt_ms")
    delta_tt_ms = total("delta_tt_ms")

    return {
        "depth": depth,
        "position_count": len(records),
        "action_equivalence": True,
        "search_and_cache_equivalence_to_prior_combined": True,
        "baseline_nodes": baseline_nodes,
        "combined_expanded_nodes": combined_nodes,
        "cache_hits": cache_hits,
        "combined_node_reduction_vs_baseline": (
            1.0 - combined_nodes / baseline_nodes if baseline_nodes else 0.0
        ),
        "baseline_ms": baseline_ms,
        "score_tt_ms": score_tt_ms,
        "delta_tt_ms": delta_tt_ms,
        "score_tt_over_baseline": score_tt_ms / baseline_ms if baseline_ms else 0.0,
        "delta_tt_over_baseline": delta_tt_ms / baseline_ms if baseline_ms else 0.0,
        "delta_tt_over_score_tt": delta_tt_ms / score_tt_ms if score_tt_ms else 0.0,
        "records": records,
    }


def run(depths: tuple[int, ...]) -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "experiment": "delta-ordering-plus-structural-exact-tt",
        "suite_id": POSITION_SUITE_ID,
        "rules_mode": "candidate",
        "position_count": 16,
        "hypothesis": (
            "Replacing full child score recomputation with the proven delta-equivalent "
            "ordering calculation lowers the runtime cost of the existing score-order + "
            "structural exact-TT engine without changing its actions, traversal, or hits."
        ),
        "depths": [_run_depth(depth) for depth in depths],
        "source_fingerprints": {
            "baseline_ai_sha256": _source_fingerprint("crownline_ai.py"),
            "prior_combined_sha256": _source_fingerprint("crownline_combined_search.py"),
            "delta_combined_sha256": _source_fingerprint("crownline_delta_tt.py"),
            "position_suite_sha256": _source_fingerprint(
                str(POSITION_SUITE_PATH.relative_to(ROOT))
            ),
            "experiment_sha256": _source_fingerprint(
                "experiments/benchmark_delta_ordering_plus_tt.py"
            ),
        },
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compare score-order TT with delta-equivalent score-order TT."
    )
    parser.add_argument("--depths", type=int, nargs="+", default=(2, 3, 4), choices=range(1, 5))
    parser.add_argument("--json", dest="json_path", default=None)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    report = run(tuple(args.depths))
    print("Crownline delta-order + structural-TT benchmark")
    print(f"Suite {report['suite_id']} | positions {report['position_count']}")
    for result in report["depths"]:
        print(
            f"d{result['depth']}: tree/cache-equivalent={result['search_and_cache_equivalence_to_prior_combined']} | "
            f"nodes {result['baseline_nodes']} -> {result['combined_expanded_nodes']} | "
            f"delta-TT {result['delta_tt_over_baseline']:.2f}x baseline / "
            f"{result['delta_tt_over_score_tt']:.2f}x prior combined"
        )
    if args.json_path:
        path = Path(args.json_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"JSON report: {path}")


if __name__ == "__main__":
    main()
