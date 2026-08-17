from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from statistics import mean

from crownline_benchmark import BaselineEngine, _source_fingerprint
from crownline_position_suite import POSITION_SUITE_ID, POSITION_SUITE_PATH, position_suite
from crownline_set import CrownlineSet
from crownline_time_engines import choose_computer_action_iterative_baseline
from crownline_tt_time_engine import choose_computer_action_iterative_structural_tt


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = 1


def _state_for_fixture(fixture) -> CrownlineSet:
    return CrownlineSet(
        first_game_white="A",
        current_game=fixture.game(),
        rules_mode="candidate",
    )


def _action_label(notation, meld_line) -> str:
    return notation + (f" | {'-'.join(meld_line)}" if meld_line else "")


def _position_rows():
    rows = []
    for scenario in position_suite():
        for game_number, fixture in ((1, scenario.game1), (2, scenario.game2)):
            state = _state_for_fixture(fixture)
            rows.append(
                (
                    scenario.scenario_id,
                    game_number,
                    fixture,
                    state,
                    state.participant_for_color(state.current_game.turn),
                )
            )
    return tuple(rows)


def _fixed_references(rows, max_depth: int) -> dict:
    references = {}
    for scenario_id, game_number, fixture, state, participant in rows:
        by_depth = {}
        for depth in range(1, max_depth + 1):
            decision = BaselineEngine(
                f"reference-{scenario_id}-g{game_number}-d{depth}",
                depth=depth,
            ).choose(state, participant)
            by_depth[depth] = {
                "action": _action_label(decision.notation, decision.meld_line),
                "search_nodes": decision.search_nodes,
                "elapsed_ms": decision.elapsed_ms,
            }
        references[fixture.fingerprint] = by_depth
    return references


def _validate_baseline_iterations(stats, references, fingerprint, scenario_id, game_number):
    matches = []
    for iteration in stats.iterations:
        if not iteration.completed:
            continue
        reference = references[fingerprint][iteration.depth]
        action = _action_label(iteration.notation, iteration.meld_line)
        action_match = action == reference["action"]
        node_match = iteration.search_nodes == reference["search_nodes"]
        if not action_match or not node_match:
            raise AssertionError(
                f"Baseline iterative mismatch at {scenario_id} Game {game_number} "
                f"depth {iteration.depth}: action={action!r} vs {reference['action']!r}, "
                f"nodes={iteration.search_nodes} vs {reference['search_nodes']}"
            )
        matches.append(action_match and node_match)
    return all(matches)


def _validate_tt_iterations(stats, references, fingerprint, scenario_id, game_number):
    matches = []
    for iteration in stats.iterations:
        if not iteration.completed:
            continue
        reference = references[fingerprint][iteration.depth]
        action = _action_label(iteration.notation, iteration.meld_line)
        action_match = action == reference["action"]
        if not action_match:
            raise AssertionError(
                f"Structural-TT iterative mismatch at {scenario_id} Game {game_number} "
                f"depth {iteration.depth}: action={action!r} vs {reference['action']!r}"
            )
        matches.append(action_match)
    return all(matches)


def _depth_distribution(records, key: str, max_depth: int) -> dict:
    counts = Counter(record[key] for record in records)
    return {str(depth): counts.get(depth, 0) for depth in range(0, max_depth + 1)}


def _run_budget(
    rows,
    references: dict,
    *,
    budget_ms: float,
    max_depth: int,
    budget_index: int,
) -> dict:
    records = []

    for position_index, (scenario_id, game_number, fixture, state, participant) in enumerate(rows):
        # Alternate pair order to reduce systematic warm-cache / runner-order bias.
        baseline_first = (position_index + budget_index) % 2 == 0
        if baseline_first:
            baseline_choice = choose_computer_action_iterative_baseline(
                state,
                participant=participant,
                budget_ms=budget_ms,
                max_depth=max_depth,
            )
            tt_choice = choose_computer_action_iterative_structural_tt(
                state,
                participant=participant,
                budget_ms=budget_ms,
                max_depth=max_depth,
            )
        else:
            tt_choice = choose_computer_action_iterative_structural_tt(
                state,
                participant=participant,
                budget_ms=budget_ms,
                max_depth=max_depth,
            )
            baseline_choice = choose_computer_action_iterative_baseline(
                state,
                participant=participant,
                budget_ms=budget_ms,
                max_depth=max_depth,
            )

        baseline_notation, baseline_meld, baseline_stats = baseline_choice
        tt_notation, tt_meld, tt_stats = tt_choice

        baseline_equivalent = _validate_baseline_iterations(
            baseline_stats,
            references,
            fixture.fingerprint,
            scenario_id,
            game_number,
        )
        tt_equivalent = _validate_tt_iterations(
            tt_stats,
            references,
            fixture.fingerprint,
            scenario_id,
            game_number,
        )

        if baseline_stats.completed_depth > 0:
            baseline_return_match = (
                _action_label(baseline_notation, baseline_meld)
                == references[fixture.fingerprint][baseline_stats.completed_depth]["action"]
            )
        else:
            baseline_return_match = None

        if tt_stats.completed_depth > 0:
            tt_return_match = (
                _action_label(tt_notation, tt_meld)
                == references[fixture.fingerprint][tt_stats.completed_depth]["action"]
            )
        else:
            tt_return_match = None

        if baseline_return_match is False or tt_return_match is False:
            raise AssertionError(
                f"Returned action mismatch at {scenario_id} Game {game_number}"
            )

        depth_delta = tt_stats.completed_depth - baseline_stats.completed_depth
        records.append(
            {
                "scenario_id": scenario_id,
                "game_number": game_number,
                "position_fingerprint": fixture.fingerprint,
                "participant": participant,
                "budget_ms": budget_ms,
                "run_order": "baseline-first" if baseline_first else "tt-first",
                "baseline_completed_depth": baseline_stats.completed_depth,
                "tt_completed_depth": tt_stats.completed_depth,
                "depth_delta_tt_minus_baseline": depth_delta,
                "tt_deeper": depth_delta > 0,
                "same_depth": depth_delta == 0,
                "tt_shallower": depth_delta < 0,
                "baseline_timed_out": baseline_stats.timed_out,
                "tt_timed_out": tt_stats.timed_out,
                "baseline_elapsed_ms": baseline_stats.elapsed_ms,
                "tt_elapsed_ms": tt_stats.elapsed_ms,
                "baseline_deadline_overrun_ms": baseline_stats.deadline_overrun_ms,
                "tt_deadline_overrun_ms": tt_stats.deadline_overrun_ms,
                "baseline_total_search_nodes": baseline_stats.total_search_nodes,
                "tt_total_expanded_nodes": tt_stats.total_expanded_nodes,
                "tt_total_cache_hits": tt_stats.total_cache_hits,
                "tt_final_cache_size": tt_stats.final_cache_size,
                "baseline_completed_iterations_equivalent": baseline_equivalent,
                "tt_completed_iterations_equivalent": tt_equivalent,
                "baseline_returned_action_matches_fixed": baseline_return_match,
                "tt_returned_action_matches_fixed": tt_return_match,
                "baseline_returned_action": _action_label(baseline_notation, baseline_meld),
                "tt_returned_action": _action_label(tt_notation, tt_meld),
            }
        )

    baseline_depths = [record["baseline_completed_depth"] for record in records]
    tt_depths = [record["tt_completed_depth"] for record in records]
    deltas = [record["depth_delta_tt_minus_baseline"] for record in records]

    return {
        "budget_ms": budget_ms,
        "position_count": len(records),
        "baseline_depth_distribution": _depth_distribution(
            records,
            "baseline_completed_depth",
            max_depth,
        ),
        "tt_depth_distribution": _depth_distribution(
            records,
            "tt_completed_depth",
            max_depth,
        ),
        "baseline_mean_completed_depth": mean(baseline_depths),
        "tt_mean_completed_depth": mean(tt_depths),
        "mean_depth_gain_tt_minus_baseline": mean(deltas),
        "net_completed_depth_gain": sum(deltas),
        "tt_deeper_positions": sum(delta > 0 for delta in deltas),
        "same_depth_positions": sum(delta == 0 for delta in deltas),
        "tt_shallower_positions": sum(delta < 0 for delta in deltas),
        "baseline_positions_reaching_max_depth": sum(
            depth == max_depth for depth in baseline_depths
        ),
        "tt_positions_reaching_max_depth": sum(depth == max_depth for depth in tt_depths),
        "baseline_fallbacks": sum(depth == 0 for depth in baseline_depths),
        "tt_fallbacks": sum(depth == 0 for depth in tt_depths),
        "all_baseline_completed_iterations_equivalent": all(
            record["baseline_completed_iterations_equivalent"] for record in records
        ),
        "all_tt_completed_iterations_equivalent": all(
            record["tt_completed_iterations_equivalent"] for record in records
        ),
        "baseline_mean_elapsed_ms": mean(
            record["baseline_elapsed_ms"] for record in records
        ),
        "tt_mean_elapsed_ms": mean(record["tt_elapsed_ms"] for record in records),
        "baseline_max_overrun_ms": max(
            record["baseline_deadline_overrun_ms"] for record in records
        ),
        "tt_max_overrun_ms": max(
            record["tt_deadline_overrun_ms"] for record in records
        ),
        "baseline_mean_total_search_nodes": mean(
            record["baseline_total_search_nodes"] for record in records
        ),
        "tt_mean_total_expanded_nodes": mean(
            record["tt_total_expanded_nodes"] for record in records
        ),
        "tt_total_cache_hits": sum(record["tt_total_cache_hits"] for record in records),
        "tt_mean_cache_hits": mean(record["tt_total_cache_hits"] for record in records),
        "records": records,
    }


def run(budgets_ms: tuple[float, ...], max_depth: int = 4) -> dict:
    rows = _position_rows()
    references = _fixed_references(rows, max_depth)
    results = [
        _run_budget(
            rows,
            references,
            budget_ms=budget_ms,
            max_depth=max_depth,
            budget_index=index,
        )
        for index, budget_ms in enumerate(budgets_ms)
    ]

    return {
        "schema_version": SCHEMA_VERSION,
        "experiment": "iterative-time-budget-structural-tt-comparison",
        "suite_id": POSITION_SUITE_ID,
        "rules_mode": "candidate",
        "position_count": len(rows),
        "budgets_ms": list(budgets_ms),
        "max_depth": max_depth,
        "hypothesis": (
            "The validated CLSN-equivalent structural exact transposition table, "
            "persisted across iterative-deepening depths, lets Baseline A complete "
            "deeper exact searches under the same wall-clock budget without changing "
            "the action of any fully completed depth."
        ),
        "comparison_policy": (
            "For every frozen position and budget, baseline iterative deepening and "
            "structural-TT iterative deepening are run as a pair with alternating "
            "execution order. Both use the same evaluator, action order, depth cap, "
            "soft deadline policy, and fixed-depth Baseline A action references."
        ),
        "budgets": results,
        "source_fingerprints": {
            "baseline_ai_sha256": _source_fingerprint("crownline_ai.py"),
            "benchmark_harness_sha256": _source_fingerprint("crownline_benchmark.py"),
            "clsn_sha256": _source_fingerprint("crownline_state_notation.py"),
            "baseline_time_engine_sha256": _source_fingerprint("crownline_time_engines.py"),
            "structural_tt_search_sha256": _source_fingerprint("crownline_search_engines.py"),
            "tt_time_engine_sha256": _source_fingerprint("crownline_tt_time_engine.py"),
            "position_suite_sha256": _source_fingerprint(
                str(POSITION_SUITE_PATH.relative_to(ROOT))
            ),
            "experiment_sha256": _source_fingerprint(
                "experiments/benchmark_iterative_tt_time_budget.py"
            ),
        },
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Compare baseline and structural-TT iterative deepening on frozen Crownline positions."
        )
    )
    parser.add_argument(
        "--budgets-ms",
        type=float,
        nargs="+",
        default=(50.0, 150.0, 500.0, 1000.0),
    )
    parser.add_argument("--max-depth", type=int, default=4, choices=range(1, 5))
    parser.add_argument("--json", dest="json_path", default=None)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    if any(value <= 0 for value in args.budgets_ms):
        raise SystemExit("All budgets must be positive")

    report = run(tuple(args.budgets_ms), max_depth=args.max_depth)
    print("Crownline iterative time-budget structural-TT comparison")
    print(f"Suite {report['suite_id']} | positions {report['position_count']}")
    for result in report["budgets"]:
        print(
            f"{result['budget_ms']:g} ms: baseline mean d{result['baseline_mean_completed_depth']:.2f} "
            f"vs TT d{result['tt_mean_completed_depth']:.2f} | "
            f"deeper/same/shallower {result['tt_deeper_positions']}/"
            f"{result['same_depth_positions']}/{result['tt_shallower_positions']} | "
            f"max-depth {result['baseline_positions_reaching_max_depth']} -> "
            f"{result['tt_positions_reaching_max_depth']} | "
            f"TT equivalent={result['all_tt_completed_iterations_equivalent']}"
        )

    if args.json_path:
        path = Path(args.json_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"JSON report: {path}")


if __name__ == "__main__":
    main()
