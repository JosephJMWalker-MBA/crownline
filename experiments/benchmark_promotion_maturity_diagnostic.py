from __future__ import annotations

import argparse
import json
from pathlib import Path

import crownline_ai
from crownline_benchmark import _source_fingerprint
from crownline_king_position_suite import (
    KING_POSITION_SUITE_PATH,
    king_position_suite,
)
from crownline_position_suite import POSITION_SUITE_PATH, position_suite
from crownline_promotion_maturity_experiment import choose_promotion_maturity_action
from crownline_set import CrownlineSet
from experiments.diagnose_stage3_cycle import (
    CYCLE_MOVES,
    CYCLE_START_CLSN,
    _apply_named_action,
    _set_for_clsn,
)


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = 1


def _state(game) -> CrownlineSet:
    return CrownlineSet(
        first_game_white="A",
        current_game=game,
        rules_mode="candidate",
    )


def _early_fixtures():
    for scenario in position_suite():
        yield f"{scenario.scenario_id}:game1", scenario.game1
        yield f"{scenario.scenario_id}:game2", scenario.game2


def _king_fixtures():
    for fixture in king_position_suite():
        yield fixture.fixture_id, fixture


def _root_policy_changes(fixtures, *, depth: int, weight: float) -> dict:
    changes = []
    positions = 0
    for fixture_id, fixture in fixtures:
        state = _state(fixture.game())
        participant = state.participant_for_color(state.current_game.turn)
        baseline = crownline_ai.choose_computer_action(
            state,
            participant=participant,
            depth=depth,
        )
        candidate = choose_promotion_maturity_action(
            state,
            participant,
            depth=depth,
            maturity_weight=weight,
        )
        positions += 1
        if candidate != baseline:
            changes.append(
                {
                    "fixture_id": fixture_id,
                    "participant": participant,
                    "baseline": {
                        "move": baseline[0],
                        "meld_line": baseline[1],
                    },
                    "candidate": {
                        "move": candidate[0],
                        "meld_line": candidate[1],
                    },
                }
            )
    return {
        "positions": positions,
        "changed_actions": len(changes),
        "unchanged_actions": positions - len(changes),
        "changes": changes,
    }


def _cycle_states():
    states = []
    cursor = _set_for_clsn(CYCLE_START_CLSN)
    for move in CYCLE_MOVES:
        states.append((cursor, move))
        cursor = _apply_named_action(cursor, move)
    return states


def _cycle_policy(depth: int, weight: float) -> dict:
    rows = []
    selected_cycle = 0
    for index, (state, cycle_move) in enumerate(_cycle_states(), start=1):
        participant = state.participant_for_color(state.current_game.turn)
        selected = choose_promotion_maturity_action(
            state,
            participant,
            depth=depth,
            maturity_weight=weight,
        )
        chose_cycle = selected[0] == cycle_move
        selected_cycle += int(chose_cycle)
        rows.append(
            {
                "state": index,
                "turn": state.current_game.turn,
                "participant": participant,
                "cycle_move": cycle_move,
                "selected_move": selected[0],
                "selected_meld_line": selected[1],
                "chose_cycle": chose_cycle,
            }
        )
    return {
        "depth": depth,
        "cycle_moves_selected": selected_cycle,
        "states": 4,
        "rows": rows,
    }


def run(weights: tuple[float, ...], *, root_depth: int) -> dict:
    points = []
    for weight in weights:
        points.append(
            {
                "maturity_weight": weight,
                "early_root": _root_policy_changes(
                    _early_fixtures(),
                    depth=root_depth,
                    weight=weight,
                ),
                "king_root": _root_policy_changes(
                    _king_fixtures(),
                    depth=root_depth,
                    weight=weight,
                ),
                "preserved_cycle_depth2": _cycle_policy(2, weight),
                "preserved_cycle_depth3": _cycle_policy(3, weight),
            }
        )

    return {
        "schema_version": SCHEMA_VERSION,
        "experiment": "stage3-promotion-maturity-root-diagnostic",
        "rules_mode": "candidate",
        "root_depth": root_depth,
        "weights": list(weights),
        "hypothesis": (
            "Continuous promotion maturity should preserve the strategic value of crowning by "
            "moving smoothly from ordinary-piece progress to King=1.0. The first gate is whether "
            "small weights alter only a restrained number of early and King-rich root decisions "
            "while avoiding the semantic cliff of pure promotion proximity."
        ),
        "points": points,
        "source_fingerprints": {
            "baseline_ai_sha256": _source_fingerprint("crownline_ai.py"),
            "maturity_experiment_sha256": _source_fingerprint(
                "crownline_promotion_maturity_experiment.py"
            ),
            "early_position_suite_sha256": _source_fingerprint(
                str(POSITION_SUITE_PATH.relative_to(ROOT))
            ),
            "king_position_suite_sha256": _source_fingerprint(
                str(KING_POSITION_SUITE_PATH.relative_to(ROOT))
            ),
            "diagnostic_sha256": _source_fingerprint(
                "experiments/benchmark_promotion_maturity_diagnostic.py"
            ),
        },
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Sweep continuous promotion-maturity weights across both frozen root guardrails."
    )
    parser.add_argument(
        "--weights",
        nargs="+",
        type=float,
        default=(0.0, 10.0, 25.0, 50.0, 100.0, 200.0, 400.0),
    )
    parser.add_argument("--root-depth", type=int, default=3, choices=range(1, 5))
    parser.add_argument("--json", dest="json_path", default=None)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    weights = tuple(float(value) for value in args.weights)
    if any(value < 0 for value in weights):
        raise SystemExit("weights must be non-negative")
    report = run(weights, root_depth=args.root_depth)
    print("Crownline Stage 3 promotion-maturity root diagnostic")
    print(f"root_depth={report['root_depth']} weights={tuple(report['weights'])}")
    for point in report["points"]:
        early = point["early_root"]
        king = point["king_root"]
        d2 = point["preserved_cycle_depth2"]
        d3 = point["preserved_cycle_depth3"]
        print(
            f"w={point['maturity_weight']:g}: early changes "
            f"{early['changed_actions']}/{early['positions']} | King changes "
            f"{king['changed_actions']}/{king['positions']} | cycle selected d2 "
            f"{d2['cycle_moves_selected']}/4 | d3 {d3['cycle_moves_selected']}/4"
        )
        if early["changes"]:
            print(
                "  early: "
                + "; ".join(
                    f"{item['fixture_id']} {item['baseline']['move']}->{item['candidate']['move']}"
                    for item in early["changes"]
                )
            )
        if king["changes"]:
            print(
                "  King: "
                + "; ".join(
                    f"{item['fixture_id']} {item['baseline']['move']}->{item['candidate']['move']}"
                    for item in king["changes"]
                )
            )
    if args.json_path:
        path = Path(args.json_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(f"JSON report: {path}")


if __name__ == "__main__":
    main()
