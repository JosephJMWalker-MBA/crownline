from __future__ import annotations

import argparse
import json
from pathlib import Path

from crownline_benchmark import BaselineEngine, _source_fingerprint
from crownline_position_suite import POSITION_SUITE_ID, POSITION_SUITE_PATH, position_suite
from crownline_search_engines import ExactStructuralTTBaselineEngine, ExactTTBaselineEngine
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
    clsn_tt = ExactTTBaselineEngine(f"clsn-tt-d{depth}", depth=depth)
    structural_tt = ExactStructuralTTBaselineEngine(
        f"structural-tt-d{depth}",
        depth=depth,
    )

    baseline_nodes = 0
    clsn_nodes = 0
    structural_nodes = 0
    baseline_ms = 0.0
    clsn_ms = 0.0
    structural_ms = 0.0
    records = []

    for scenario in position_suite():
        for game_number, fixture in ((1, scenario.game1), (2, scenario.game2)):
            state = _state_for_fixture(fixture)
            participant = state.participant_for_color(state.current_game.turn)

            clsn_hits_before = clsn_tt.total_cache_hits
            structural_hits_before = structural_tt.total_cache_hits
            baseline_decision = baseline.choose(state, participant)
            clsn_decision = clsn_tt.choose(state, participant)
            structural_decision = structural_tt.choose(state, participant)
            clsn_hits = clsn_tt.total_cache_hits - clsn_hits_before
            structural_hits = structural_tt.total_cache_hits - structural_hits_before

            baseline_action = (baseline_decision.notation, baseline_decision.meld_line)
            clsn_action = (clsn_decision.notation, clsn_decision.meld_line)
            structural_action = (structural_decision.notation, structural_decision.meld_line)
            if not (baseline_action == clsn_action == structural_action):
                raise AssertionError(
                    f"Action mismatch at {scenario.scenario_id} Game {game_number}: "
                    f"baseline={baseline_action}, clsn={clsn_action}, structural={structural_action}"
                )
            if clsn_decision.search_nodes != structural_decision.search_nodes:
                raise AssertionError(
                    f"Expanded-node mismatch at {scenario.scenario_id} Game {game_number}"
                )
            if clsn_hits != structural_hits:
                raise AssertionError(
                    f"Cache-hit mismatch at {scenario.scenario_id} Game {game_number}"
                )

            baseline_nodes += baseline_decision.search_nodes
            clsn_nodes += clsn_decision.search_nodes
            structural_nodes += structural_decision.search_nodes
            baseline_ms += baseline_decision.elapsed_ms
            clsn_ms += clsn_decision.elapsed_ms
            structural_ms += structural_decision.elapsed_ms
            records.append(
                {
                    "scenario_id": scenario.scenario_id,
                    "game_number": game_number,
                    "fingerprint": fixture.fingerprint,
                    "baseline_nodes": baseline_decision.search_nodes,
                    "tt_expanded_nodes": structural_decision.search_nodes,
                    "cache_hits": structural_hits,
                    "baseline_ms": baseline_decision.elapsed_ms,
                    "clsn_tt_ms": clsn_decision.elapsed_ms,
                    "structural_tt_ms": structural_decision.elapsed_ms,
                }
            )

    hits = structural_tt.total_cache_hits
    probes = structural_nodes + hits
    return {
        "depth": depth,
        "position_count": len(records),
        "action_equivalence": True,
        "search_count_equivalence_between_tt_keys": True,
        "baseline_nodes": baseline_nodes,
        "tt_expanded_nodes": structural_nodes,
        "cache_hits": hits,
        "cache_hit_rate": hits / probes if probes else 0.0,
        "expanded_node_reduction_fraction": (
            1.0 - structural_nodes / baseline_nodes if baseline_nodes else 0.0
        ),
        "baseline_ms": baseline_ms,
        "clsn_tt_ms": clsn_ms,
        "structural_tt_ms": structural_ms,
        "clsn_tt_over_baseline": clsn_ms / baseline_ms if baseline_ms else 0.0,
        "structural_tt_over_baseline": (
            structural_ms / baseline_ms if baseline_ms else 0.0
        ),
        "structural_over_clsn_tt": (
            structural_ms / clsn_ms if clsn_ms else 0.0
        ),
        "records": records,
    }


def run(depths: tuple[int, ...]) -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "experiment": "exact-tt-key-representation",
        "suite_id": POSITION_SUITE_ID,
        "rules_mode": "candidate",
        "position_count": 16,
        "hypothesis": (
            "A structural key encoding the same future-relevant CLSN1 facts "
            "preserves exact-TT search behavior while removing enough string "
            "serialization overhead to improve wall-clock performance."
        ),
        "depths": [_run_depth(depth) for depth in depths],
        "source_fingerprints": {
            "baseline_ai_sha256": _source_fingerprint("crownline_ai.py"),
            "clsn_sha256": _source_fingerprint("crownline_state_notation.py"),
            "tt_engine_sha256": _source_fingerprint("crownline_search_engines.py"),
            "position_suite_sha256": _source_fingerprint(
                str(POSITION_SUITE_PATH.relative_to(ROOT))
            ),
            "experiment_sha256": _source_fingerprint(
                "experiments/benchmark_tt_key_strategy.py"
            ),
        },
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compare CLSN-string and structural exact transposition keys."
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
    print("Crownline exact-TT key benchmark")
    print(f"Suite {report['suite_id']} | positions {report['position_count']}")
    for result in report["depths"]:
        print(
            f"d{result['depth']}: nodes {result['baseline_nodes']} -> "
            f"{result['tt_expanded_nodes']} | hits {result['cache_hits']} | "
            f"CLSN TT {result['clsn_tt_over_baseline']:.2f}x baseline | "
            f"structural TT {result['structural_tt_over_baseline']:.2f}x baseline | "
            f"structural/CLSN {result['structural_over_clsn_tt']:.2f}x"
        )
    if args.json_path:
        path = Path(args.json_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"JSON report: {path}")


if __name__ == "__main__":
    main()
