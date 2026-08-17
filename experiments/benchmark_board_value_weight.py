from __future__ import annotations

import argparse
import json
from pathlib import Path

from crownline_ai import _actions, choose_computer_action
from crownline_benchmark import _source_fingerprint
from crownline_evaluator_experiments import choose_board_weighted_action
from crownline_position_suite import POSITION_SUITE_ID, POSITION_SUITE_PATH, position_suite
from crownline_set import CrownlineSet
from crownline_state_notation import clsn_fingerprint, parse_clsn, serialize_clsn


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = 1

CYCLE_CASES = (
    {
        "id": "baseline-d2-game1",
        "source": "benchmarks/baseline_d2_vs_d2_repetition_summary.json",
        "clsn": (
            "CLSN1|g=1|r=candidate|t=W|b=6,7|q=-|o=0|e=-|"
            "p=a5:W3,b4:B1K,b6:W6,d4:B3,d6:W5K,g5:B5K,h4:B6|"
            "mw=-|mb=b4.d4.f4:5.3.1:15:0|cw=-|cb=-"
        ),
        "moves": ("d6-e5", "b4-c3", "e5-d6", "c3-b4"),
    },
    {
        "id": "d2-vs-d3-game2",
        "source": "benchmarks/depth2_vs_depth3_diagnostic_summary.json",
        "clsn": (
            "CLSN1|g=2|r=candidate|t=W|b=7,6|q=-|o=0|e=-|"
            "p=a2:B5,b3:B4K,c4:W6K,c6:W4,d3:B2,d7:W5K,f5:B3K|"
            "mw=-|mb=g4.e4.c4:3.4.2:15:0|cw=-|cb=-"
        ),
        "moves": ("c4-d5", "b3-a4", "d5-c4", "a4-b3"),
    },
)


def _set_for_clsn(clsn: str) -> CrownlineSet:
    game = parse_clsn(clsn)
    return CrownlineSet(
        first_game_white="A",
        current_game=game,
        rules_mode="candidate",
    )


def _action_text(action) -> str:
    notation, meld_line = action
    return notation + (f" | {'-'.join(meld_line)}" if meld_line else "")


def _apply_named_action(state: CrownlineSet, notation: str) -> CrownlineSet:
    matches = [
        (move, meld_line)
        for move, meld_line in _actions(state)
        if move.notation() == notation
    ]
    if len(matches) != 1:
        raise AssertionError(f"Expected one legal action for {notation!r}, found {len(matches)}")
    move, meld_line = matches[0]
    return state.apply_move(move, meld_line=meld_line)


def _cycle_states(case: dict) -> list[CrownlineSet]:
    start = _set_for_clsn(case["clsn"])
    if serialize_clsn(start.current_game) != case["clsn"]:
        raise AssertionError(f"{case['id']} CLSN is not canonical")
    states = [start]
    cursor = start
    for notation in case["moves"]:
        cursor = _apply_named_action(cursor, notation)
        states.append(cursor)
    if serialize_clsn(states[-1].current_game) != case["clsn"]:
        raise AssertionError(f"{case['id']} does not round-trip after four recorded moves")
    return states[:4]


def _cycle_result(weight: float, depth: int) -> dict:
    cases = []
    total_cycle_selected = 0
    total_decisions = 0
    for case in CYCLE_CASES:
        states = _cycle_states(case)
        rows = []
        selected_count = 0
        for index, state in enumerate(states):
            participant = state.participant_for_color(state.current_game.turn)
            selected = choose_board_weighted_action(
                state,
                participant,
                depth=depth,
                board_weight=weight,
            )
            selected_text = _action_text(selected)
            cycle_move = case["moves"][index]
            is_cycle = selected_text.split(" | ", 1)[0] == cycle_move
            selected_count += int(is_cycle)
            rows.append(
                {
                    "state_index": index + 1,
                    "fingerprint": clsn_fingerprint(state.current_game),
                    "turn": state.current_game.turn,
                    "participant": participant,
                    "cycle_move": cycle_move,
                    "selected_action": selected_text,
                    "selected_cycle_move": is_cycle,
                }
            )
        total_cycle_selected += selected_count
        total_decisions += len(rows)
        cases.append(
            {
                "case_id": case["id"],
                "cycle_moves_selected": selected_count,
                "decisions": len(rows),
                "fully_reproduces_cycle_policy": selected_count == len(rows),
                "states": rows,
            }
        )
    return {
        "board_weight": weight,
        "depth": depth,
        "cycle_moves_selected": total_cycle_selected,
        "cycle_decisions": total_decisions,
        "cycle_selection_fraction": total_cycle_selected / total_decisions,
        "cases": cases,
    }


def _frozen_suite_result(weight: float, depth: int) -> dict:
    changed = []
    for scenario in position_suite():
        for game_number, fixture in ((1, scenario.game1), (2, scenario.game2)):
            state = CrownlineSet(
                first_game_white="A",
                current_game=fixture.game(),
                rules_mode="candidate",
            )
            participant = state.participant_for_color(state.current_game.turn)
            baseline = _action_text(
                choose_computer_action(
                    state,
                    participant=participant,
                    depth=depth,
                )
            )
            candidate = _action_text(
                choose_board_weighted_action(
                    state,
                    participant,
                    depth=depth,
                    board_weight=weight,
                )
            )
            if baseline != candidate:
                changed.append(
                    {
                        "scenario_id": scenario.scenario_id,
                        "game_number": game_number,
                        "fingerprint": fixture.fingerprint,
                        "baseline_action": baseline,
                        "candidate_action": candidate,
                    }
                )
    return {
        "board_weight": weight,
        "depth": depth,
        "positions": 16,
        "changed_actions": len(changed),
        "unchanged_actions": 16 - len(changed),
        "changed_fraction": len(changed) / 16.0,
        "changes": changed,
    }


def run(weights: tuple[float, ...], depths: tuple[int, ...]) -> dict:
    cycle_results = [
        _cycle_result(weight, depth)
        for depth in depths
        for weight in weights
    ]
    suite_results = [
        _frozen_suite_result(weight, depth)
        for depth in depths
        for weight in weights
    ]

    for depth in depths:
        baseline_cycle = next(
            result
            for result in cycle_results
            if result["depth"] == depth and result["board_weight"] == 1.0
        )
        # The preserved cycles are matchup-specific, so not every depth must
        # reproduce every move. Weight 1.0 must nevertheless match Baseline A
        # on the frozen general position suite exactly.
        baseline_suite = next(
            result
            for result in suite_results
            if result["depth"] == depth and result["board_weight"] == 1.0
        )
        if baseline_suite["changed_actions"] != 0:
            raise AssertionError(f"board_weight=1.0 changed Baseline A policy at depth {depth}")
        if baseline_cycle["cycle_decisions"] != 8:
            raise AssertionError("Expected eight preserved cycle decision states")

    return {
        "schema_version": SCHEMA_VERSION,
        "experiment": "stage3-nonterminal-board-value-weight",
        "suite_id": POSITION_SUITE_ID,
        "rules_mode": "candidate",
        "weights": list(weights),
        "depths": list(depths),
        "hypothesis": (
            "Baseline A overweights provisional board-square score at nonterminal nodes. "
            "Reducing only that term, while keeping capture bank, banked Crownline bonus, "
            "terminal scoring, mobility, rules, search depth, and tie-breaking unchanged, "
            "should reduce preference for reversible four-ply cycles."
        ),
        "experimental_boundary": (
            "board_weight=1.0 is Baseline A. Only nonterminal board_value margin is scaled; "
            "terminal evaluation always uses the full authoritative Crownline score."
        ),
        "cycle_cases": [
            {
                "case_id": case["id"],
                "source": case["source"],
                "start_clsn": case["clsn"],
                "start_fingerprint": clsn_fingerprint(parse_clsn(case["clsn"])),
                "moves": list(case["moves"]),
            }
            for case in CYCLE_CASES
        ],
        "cycle_results": cycle_results,
        "frozen_suite_results": suite_results,
        "source_fingerprints": {
            "baseline_ai_sha256": _source_fingerprint("crownline_ai.py"),
            "experimental_evaluator_sha256": _source_fingerprint(
                "crownline_evaluator_experiments.py"
            ),
            "experiment_sha256": _source_fingerprint(
                "experiments/benchmark_board_value_weight.py"
            ),
            "position_suite_sha256": _source_fingerprint(
                str(POSITION_SUITE_PATH.relative_to(ROOT))
            ),
            "baseline_cycle_summary_sha256": _source_fingerprint(
                "benchmarks/baseline_d2_vs_d2_repetition_summary.json"
            ),
            "mixed_depth_cycle_summary_sha256": _source_fingerprint(
                "benchmarks/depth2_vs_depth3_diagnostic_summary.json"
            ),
        },
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Test nonterminal board-value weighting against preserved Crownline cycles."
    )
    parser.add_argument(
        "--weights",
        type=float,
        nargs="+",
        default=(1.0, 0.75, 0.5, 0.25, 0.0),
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
    weights = tuple(args.weights)
    if 1.0 not in weights:
        raise ValueError("weights must include 1.0 as the Baseline A control")
    report = run(weights, tuple(args.depths))
    print("Crownline Stage 3 nonterminal board-value weighting")
    print(f"weights={weights} depths={tuple(args.depths)}")
    for result in report["cycle_results"]:
        print(
            f"d{result['depth']} w={result['board_weight']:.2f}: "
            f"cycle moves {result['cycle_moves_selected']}/{result['cycle_decisions']}"
        )
    print("Frozen-suite policy changes vs Baseline A:")
    for result in report["frozen_suite_results"]:
        print(
            f"d{result['depth']} w={result['board_weight']:.2f}: "
            f"{result['changed_actions']}/16 changed"
        )
    if args.json_path:
        path = Path(args.json_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"JSON report: {path}")


if __name__ == "__main__":
    main()
