from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from statistics import mean

from crownline_benchmark import BaselineEngine, _source_fingerprint
from crownline_position_suite import POSITION_SUITE_ID, POSITION_SUITE_PATH, position_suite
from crownline_search_engines import ExactTTBaselineEngine
from crownline_set import CrownlineSet


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = 1


@dataclass(frozen=True)
class PositionEfficiencyRecord:
    scenario_id: str
    game_number: int
    position_fingerprint: str
    participant: str
    baseline_action: str
    tt_action: str
    actions_equal: bool
    baseline_nodes: int
    tt_expanded_nodes: int
    tt_cache_hits: int
    tt_probes: int
    tt_hit_rate: float
    node_reduction_fraction: float
    baseline_ms: float
    tt_ms: float


def _state_for_fixture(fixture) -> CrownlineSet:
    game = fixture.game()
    return CrownlineSet(
        first_game_white="A",
        current_game=game,
        rules_mode="candidate",
    )


def _run_depth(depth: int) -> dict:
    baseline = BaselineEngine(f"baseline-d{depth}", depth=depth)
    tt = ExactTTBaselineEngine(f"exact-tt-d{depth}", depth=depth)
    records = []

    for scenario in position_suite():
        for game_number, fixture in ((1, scenario.game1), (2, scenario.game2)):
            state = _state_for_fixture(fixture)
            participant = state.participant_for_color(state.current_game.turn)

            before_hits = tt.total_cache_hits
            baseline_decision = baseline.choose(state, participant)
            tt_decision = tt.choose(state, participant)
            cache_hits = tt.total_cache_hits - before_hits

            baseline_action = (
                baseline_decision.notation
                + (f" | {'-'.join(baseline_decision.meld_line)}" if baseline_decision.meld_line else "")
            )
            tt_action = (
                tt_decision.notation
                + (f" | {'-'.join(tt_decision.meld_line)}" if tt_decision.meld_line else "")
            )
            actions_equal = baseline_action == tt_action
            if not actions_equal:
                raise AssertionError(
                    f"TT action mismatch at {scenario.scenario_id} Game {game_number}: "
                    f"baseline={baseline_action}, tt={tt_action}"
                )

            baseline_nodes = baseline_decision.search_nodes
            expanded = tt_decision.search_nodes
            probes = expanded + cache_hits
            records.append(
                PositionEfficiencyRecord(
                    scenario_id=scenario.scenario_id,
                    game_number=game_number,
                    position_fingerprint=fixture.fingerprint,
                    participant=participant,
                    baseline_action=baseline_action,
                    tt_action=tt_action,
                    actions_equal=actions_equal,
                    baseline_nodes=baseline_nodes,
                    tt_expanded_nodes=expanded,
                    tt_cache_hits=cache_hits,
                    tt_probes=probes,
                    tt_hit_rate=cache_hits / probes if probes else 0.0,
                    node_reduction_fraction=(
                        1.0 - expanded / baseline_nodes if baseline_nodes else 0.0
                    ),
                    baseline_ms=baseline_decision.elapsed_ms,
                    tt_ms=tt_decision.elapsed_ms,
                )
            )

    baseline_nodes_total = sum(record.baseline_nodes for record in records)
    tt_expanded_total = sum(record.tt_expanded_nodes for record in records)
    tt_hits_total = sum(record.tt_cache_hits for record in records)
    baseline_ms_total = sum(record.baseline_ms for record in records)
    tt_ms_total = sum(record.tt_ms for record in records)
    probes_total = tt_expanded_total + tt_hits_total

    return {
        "depth": depth,
        "position_count": len(records),
        "action_equivalence": all(record.actions_equal for record in records),
        "baseline_nodes": baseline_nodes_total,
        "tt_expanded_nodes": tt_expanded_total,
        "tt_cache_hits": tt_hits_total,
        "tt_probes": probes_total,
        "tt_hit_rate": tt_hits_total / probes_total if probes_total else 0.0,
        "expanded_node_reduction_fraction": (
            1.0 - tt_expanded_total / baseline_nodes_total
            if baseline_nodes_total
            else 0.0
        ),
        "baseline_ms": baseline_ms_total,
        "tt_ms": tt_ms_total,
        "latency_ratio_tt_over_baseline": (
            tt_ms_total / baseline_ms_total if baseline_ms_total else 0.0
        ),
        "mean_position_node_reduction_fraction": mean(
            record.node_reduction_fraction for record in records
        ),
        "positions_with_cache_hits": sum(record.tt_cache_hits > 0 for record in records),
        "records": [asdict(record) for record in records],
    }


def run(depths: tuple[int, ...]) -> dict:
    results = [_run_depth(depth) for depth in depths]
    return {
        "schema_version": SCHEMA_VERSION,
        "experiment": "exact-transposition-cache-efficiency",
        "suite_id": POSITION_SUITE_ID,
        "rules_mode": "candidate",
        "position_count": 16,
        "hypothesis": (
            "Exact transposition caching reduces expanded search work without "
            "changing Baseline A's chosen action."
        ),
        "cache_policy": (
            "Per-decision cache keyed by canonical CLSN1 + white participant + "
            "searching participant + remaining depth; only fully searched exact "
            "values are cached; alpha-beta cutoff bounds are not cached."
        ),
        "depths": results,
        "source_fingerprints": {
            "baseline_ai_sha256": _source_fingerprint("crownline_ai.py"),
            "benchmark_harness_sha256": _source_fingerprint("crownline_benchmark.py"),
            "clsn_sha256": _source_fingerprint("crownline_state_notation.py"),
            "tt_engine_sha256": _source_fingerprint("crownline_search_engines.py"),
            "position_suite_sha256": _source_fingerprint(
                str(POSITION_SUITE_PATH.relative_to(ROOT))
            ),
            "experiment_sha256": _source_fingerprint("experiments/benchmark_exact_tt.py"),
        },
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Measure exact transposition caching on frozen Crownline CLSN positions."
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
    print("Crownline exact-TT efficiency benchmark")
    print(f"Suite {report['suite_id']} | positions {report['position_count']}")
    for result in report["depths"]:
        print(
            f"d{result['depth']}: equivalent={result['action_equivalence']} | "
            f"nodes {result['baseline_nodes']} -> {result['tt_expanded_nodes']} "
            f"({result['expanded_node_reduction_fraction']:.1%} reduction) | "
            f"hits {result['tt_cache_hits']} ({result['tt_hit_rate']:.1%}) | "
            f"latency ratio {result['latency_ratio_tt_over_baseline']:.2f}x"
        )
    if args.json_path:
        path = Path(args.json_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"JSON report: {path}")


if __name__ == "__main__":
    main()
