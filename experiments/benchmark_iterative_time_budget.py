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


def _reference_calibration(references: dict, max_depth: int) -> list[dict]:
    results = []
    for depth in range(1, max_depth + 1):
        values = [item[depth] for item in references.values()]
        results.append(
            {
                "depth": depth,
                "position_count": len(values),
                "total_search_nodes": sum(item["search_nodes"] for item in values),
                "mean_search_nodes": mean(item["search_nodes"] for item in values),
                "total_elapsed_ms": sum(item["elapsed_ms"] for item in values),
                "mean_elapsed_ms": mean(item["elapsed_ms"] for item in values),
                "max_elapsed_ms": max(item["elapsed_ms"] for item in values),
            }
        )
    return results


def _run_budget(rows, references: dict, *, budget_ms: float, max_depth: int) -> dict:
    records = []

    for scenario_id, game_number, fixture, state, participant in rows:
        notation, meld_line, stats = choose_computer_action_iterative_baseline(
            state,
            participant=participant,
            budget_ms=budget_ms,
            max_depth=max_depth,
        )
        returned_action = _action_label(notation, meld_line)

        iteration_records = []
        completed_iteration_matches = []
        for iteration in stats.iterations:
            reference = references[fixture.fingerprint][iteration.depth]
            if iteration.completed:
                iteration_action = _action_label(iteration.notation, iteration.meld_line)
                action_matches = iteration_action == reference["action"]
                nodes_match = iteration.search_nodes == reference["search_nodes"]
                if not action_matches or not nodes_match:
                    raise AssertionError(
                        f"Iterative mismatch at {scenario_id} Game {game_number} "
                        f"depth {iteration.depth}: action={iteration_action!r} vs "
                        f"{reference['action']!r}, nodes={iteration.search_nodes} vs "
                        f"{reference['search_nodes']}"
                    )
                completed_iteration_matches.append(action_matches and nodes_match)
            else:
                iteration_action = None
                action_matches = None
                nodes_match = None

            iteration_records.append(
                {
                    "depth": iteration.depth,
                    "completed": iteration.completed,
                    "elapsed_ms": iteration.elapsed_ms,
                    "search_nodes": iteration.search_nodes,
                    "action": iteration_action,
                    "fixed_action": reference["action"],
                    "action_matches_fixed": action_matches,
                    "nodes_match_fixed": nodes_match,
                }
            )

        if stats.completed_depth > 0:
            fixed_return = references[fixture.fingerprint][stats.completed_depth]["action"]
            returned_matches = returned_action == fixed_return
            if not returned_matches:
                raise AssertionError(
                    f"Returned iterative action mismatch at {scenario_id} Game {game_number}: "
                    f"depth {stats.completed_depth}, iterative={returned_action!r}, "
                    f"fixed={fixed_return!r}"
                )
        else:
            fixed_return = None
            returned_matches = None

        records.append(
            {
                "scenario_id": scenario_id,
                "game_number": game_number,
                "position_fingerprint": fixture.fingerprint,
                "participant": participant,
                "budget_ms": budget_ms,
                "max_depth": max_depth,
                "completed_depth": stats.completed_depth,
                "attempted_depth": stats.attempted_depth,
                "timed_out": stats.timed_out,
                "elapsed_ms": stats.elapsed_ms,
                "deadline_overrun_ms": stats.deadline_overrun_ms,
                "total_search_nodes": stats.total_search_nodes,
                "returned_action": returned_action,
                "fixed_action_at_completed_depth": fixed_return,
                "returned_action_matches_fixed": returned_matches,
                "all_completed_iterations_match_fixed": all(completed_iteration_matches),
                "iterations": iteration_records,
            }
        )

    depths = [record["completed_depth"] for record in records]
    distribution = Counter(depths)
    elapsed = sorted(record["elapsed_ms"] for record in records)
    p95_index = max(0, min(len(elapsed) - 1, int(0.95 * len(elapsed) + 0.999999) - 1))
    completed_records = [record for record in records if record["completed_depth"] > 0]

    return {
        "budget_ms": budget_ms,
        "position_count": len(records),
        "max_depth": max_depth,
        "completed_depth_distribution": {
            str(depth): distribution.get(depth, 0)
            for depth in range(0, max_depth + 1)
        },
        "mean_completed_depth": mean(depths),
        "min_completed_depth": min(depths),
        "max_completed_depth": max(depths),
        "completion_counts_by_depth": {
            str(depth): sum(value >= depth for value in depths)
            for depth in range(1, max_depth + 1)
        },
        "positions_reaching_max_depth": sum(value == max_depth for value in depths),
        "fallback_without_completed_depth": sum(value == 0 for value in depths),
        "timed_out_positions": sum(record["timed_out"] for record in records),
        "all_completed_iterations_equivalent": all(
            record["all_completed_iterations_match_fixed"] for record in records
        ),
        "returned_action_equivalence_when_depth_completed": all(
            record["returned_action_matches_fixed"] is True
            for record in completed_records
        ),
        "mean_elapsed_ms": mean(record["elapsed_ms"] for record in records),
        "p95_elapsed_ms": elapsed[p95_index],
        "max_elapsed_ms": max(elapsed),
        "max_deadline_overrun_ms": max(
            record["deadline_overrun_ms"] for record in records
        ),
        "mean_total_search_nodes": mean(
            record["total_search_nodes"] for record in records
        ),
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
        )
        for budget_ms in budgets_ms
    ]

    return {
        "schema_version": SCHEMA_VERSION,
        "experiment": "baseline-iterative-deepening-time-budget",
        "suite_id": POSITION_SUITE_ID,
        "rules_mode": "candidate",
        "position_count": len(rows),
        "budgets_ms": list(budgets_ms),
        "max_depth": max_depth,
        "hypothesis": (
            "Iterative deepening can return the deepest fully completed Baseline A "
            "search inside a practical wall-clock budget while every completed "
            "iteration remains action- and search-tree-equivalent to the same "
            "fixed-depth baseline search."
        ),
        "deadline_policy": (
            "Soft monotonic-clock deadline checked throughout root and recursive "
            "search. Partial depth iterations are discarded. The last fully "
            "completed depth is authoritative; depth-0 lexicographic fallback is "
            "used only if depth 1 cannot complete."
        ),
        "fixed_reference_calibration": _reference_calibration(references, max_depth),
        "budgets": results,
        "source_fingerprints": {
            "baseline_ai_sha256": _source_fingerprint("crownline_ai.py"),
            "benchmark_harness_sha256": _source_fingerprint("crownline_benchmark.py"),
            "clsn_sha256": _source_fingerprint("crownline_state_notation.py"),
            "time_engine_sha256": _source_fingerprint("crownline_time_engines.py"),
            "position_suite_sha256": _source_fingerprint(
                str(POSITION_SUITE_PATH.relative_to(ROOT))
            ),
            "experiment_sha256": _source_fingerprint(
                "experiments/benchmark_iterative_time_budget.py"
            ),
        },
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Measure baseline iterative deepening across frozen Crownline CLSN positions."
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
    print("Crownline baseline iterative-deepening time-budget benchmark")
    print(f"Suite {report['suite_id']} | positions {report['position_count']}")
    for result in report["budgets"]:
        print(
            f"{result['budget_ms']:g} ms: mean depth {result['mean_completed_depth']:.2f} | "
            f"distribution {result['completed_depth_distribution']} | "
            f"max-depth {result['positions_reaching_max_depth']}/{result['position_count']} | "
            f"equivalent={result['all_completed_iterations_equivalent']} | "
            f"max overrun {result['max_deadline_overrun_ms']:.2f} ms"
        )

    if args.json_path:
        path = Path(args.json_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"JSON report: {path}")


if __name__ == "__main__":
    main()
