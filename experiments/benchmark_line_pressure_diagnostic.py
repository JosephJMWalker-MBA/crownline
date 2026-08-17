from __future__ import annotations

import argparse
import json
from pathlib import Path

from crownline_ai import _actions, choose_computer_action
from crownline_benchmark import _source_fingerprint
from crownline_line_pressure_experiment import (
    choose_line_pressure_action,
    pressure_margin,
)
from crownline_position_suite import POSITION_SUITE_ID, POSITION_SUITE_PATH, position_suite
from crownline_set import CrownlineSet
from crownline_state_notation import clsn_fingerprint, parse_clsn, serialize_clsn


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = 1

# Three unique repetitions produced by Baseline d3 self-play in the complete
# Stage 3.1b frozen-suite trajectory run. Seat-symmetric duplicates are omitted.
PRIMARY_D3_CYCLES = (
    {
        "id": "d3-high-lattice-g1",
        "clsn": (
            "CLSN1|g=1|r=candidate|t=B|b=14,6|q=-|o=0|e=-|"
            "p=a3:B1K,a7:B6K,b6:W1K,b8:W6K,d4:W5K,f6:W3|"
            "mw=b6.c5.b4:1.6.2:15:0,b6.d6.f6:1.6.5:15:0,c5.e5.g5:2.3.5:15:0,d6.e5.d4:6.5.3:15:0,f6.e5.b4:3.5.1:15:0|"
            "mb=-|cw=-|cb=-"
        ),
        "moves": ("a3-b4", "b6-a5", "b4-a3", "a5-b6"),
    },
    {
        "id": "d3-quarter-cross-a-g1",
        "clsn": (
            "CLSN1|g=1|r=candidate|t=B|b=12,10|q=-|o=0|e=-|"
            "p=a5:W2K,b2:B3K,c5:W1K,d4:B5K,e3:B1,e5:W5,f6:W3|"
            "mw=b6.d6.f6:6.2.3:15:0,f6.e5.b4:3.5.2:15:0|"
            "mb=-|cw=-|cb=-"
        ),
        "moves": ("b2-a3", "a5-b6", "a3-b2", "b6-a5"),
    },
    {
        "id": "d3-full-spread-g2",
        "clsn": (
            "CLSN1|g=2|r=candidate|t=W|b=10,14|q=-|o=0|e=-|"
            "p=a2:B5K,c4:B2,d3:B4,d5:W2K,d7:W5|mw=-|mb=-|cw=-|cb=-"
        ),
        "moves": ("d5-e4", "a2-b1", "e4-d5", "b1-a2"),
    },
)

# Older preserved cycles are kept as out-of-sample secondary diagnostics. They
# are not required to be Baseline d3 cycles.
LEGACY_CYCLES = (
    {
        "id": "original-d2-g1",
        "clsn": (
            "CLSN1|g=1|r=candidate|t=W|b=6,7|q=-|o=0|e=-|"
            "p=a5:W3,b4:B1K,b6:W6,d4:B3,d6:W5K,g5:B5K,h4:B6|"
            "mw=-|mb=b4.d4.f4:5.3.1:15:0|cw=-|cb=-"
        ),
        "moves": ("d6-e5", "b4-c3", "e5-d6", "c3-b4"),
    },
    {
        "id": "mixed-d3-d2-g2",
        "clsn": (
            "CLSN1|g=2|r=candidate|t=W|b=7,6|q=-|o=0|e=-|"
            "p=a2:B5,b3:B4K,c4:W6K,c6:W4,d3:B2,d7:W5K,f5:B3K|"
            "mw=-|mb=g4.e4.c4:3.4.2:15:0|cw=-|cb=-"
        ),
        "moves": ("c4-d5", "b3-a4", "d5-c4", "a4-b3"),
    },
)


def _set_for_clsn(text: str) -> CrownlineSet:
    game = parse_clsn(text)
    return CrownlineSet(first_game_white="A", current_game=game, rules_mode="candidate")


def _apply_named_action(state: CrownlineSet, notation: str) -> CrownlineSet:
    matches = [
        (move, meld_line)
        for move, meld_line in _actions(state)
        if move.notation() == notation
    ]
    if len(matches) != 1:
        raise AssertionError(f"Expected one {notation!r} action, found {len(matches)}")
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
        raise AssertionError(f"{case['id']} does not return to its exact CLSN state")
    return states[:4]


def _action_text(action) -> str:
    notation, line = action
    return notation + (f" | {'-'.join(line)}" if line else "")


def _diagnose_cases(cases, *, weight: float, depth: int) -> dict:
    rows = []
    selected = 0
    total = 0
    for case in cases:
        states = _cycle_states(case)
        case_rows = []
        case_selected = 0
        for index, state in enumerate(states):
            participant = state.participant_for_color(state.current_game.turn)
            action = choose_line_pressure_action(
                state,
                participant,
                depth=depth,
                pressure_weight=weight,
            )
            action_text = _action_text(action)
            cycle_move = case["moves"][index]
            is_cycle = action_text.split(" | ", 1)[0] == cycle_move
            case_selected += int(is_cycle)
            case_rows.append(
                {
                    "state_index": index + 1,
                    "fingerprint": clsn_fingerprint(state.current_game),
                    "turn": state.current_game.turn,
                    "participant": participant,
                    "pressure_margin": pressure_margin(state, participant),
                    "cycle_move": cycle_move,
                    "selected_action": action_text,
                    "selected_cycle_move": is_cycle,
                }
            )
        selected += case_selected
        total += 4
        rows.append(
            {
                "case_id": case["id"],
                "cycle_moves_selected": case_selected,
                "fully_reproduces_cycle": case_selected == 4,
                "states": case_rows,
            }
        )
    return {
        "pressure_weight": weight,
        "depth": depth,
        "cycle_moves_selected": selected,
        "cycle_decisions": total,
        "cycle_selection_fraction": selected / total,
        "cases": rows,
    }


def _frozen_suite(weight: float, depth: int) -> dict:
    changes = []
    for scenario in position_suite():
        for game_number, fixture in ((1, scenario.game1), (2, scenario.game2)):
            state = CrownlineSet(
                first_game_white="A",
                current_game=fixture.game(),
                rules_mode="candidate",
            )
            participant = state.participant_for_color(state.current_game.turn)
            baseline = _action_text(
                choose_computer_action(state, participant=participant, depth=depth)
            )
            candidate = _action_text(
                choose_line_pressure_action(
                    state,
                    participant,
                    depth=depth,
                    pressure_weight=weight,
                )
            )
            if baseline != candidate:
                changes.append(
                    {
                        "scenario_id": scenario.scenario_id,
                        "game_number": game_number,
                        "fingerprint": fixture.fingerprint,
                        "baseline_action": baseline,
                        "candidate_action": candidate,
                        "pressure_margin": pressure_margin(state, participant),
                    }
                )
    return {
        "pressure_weight": weight,
        "depth": depth,
        "positions": 16,
        "changed_actions": len(changes),
        "unchanged_actions": 16 - len(changes),
        "changes": changes,
    }


def run(weights: tuple[float, ...], *, depth: int) -> dict:
    primary = [_diagnose_cases(PRIMARY_D3_CYCLES, weight=w, depth=depth) for w in weights]
    legacy = [_diagnose_cases(LEGACY_CYCLES, weight=w, depth=depth) for w in weights]
    suite = [_frozen_suite(w, depth) for w in weights]

    control = next(result for result in primary if result["pressure_weight"] == 0.0)
    if control["cycle_moves_selected"] != 12:
        raise AssertionError(
            "Weight-zero control must exactly reproduce all 12 Baseline d3 cycle decisions"
        )
    suite_control = next(result for result in suite if result["pressure_weight"] == 0.0)
    if suite_control["changed_actions"] != 0:
        raise AssertionError("Weight-zero control changed Baseline A frozen-suite policy")

    return {
        "schema_version": SCHEMA_VERSION,
        "experiment": "stage3-crownline-pressure-diagnostic",
        "suite_id": POSITION_SUITE_ID,
        "rules_mode": "candidate",
        "depth": depth,
        "weights": list(weights),
        "hypothesis": (
            "Baseline A lacks latent v1.1 Crownline geometry. Adding a small state-based "
            "construction/denial pressure term for open unretired lines should make already-"
            "crowned pieces prefer strategically productive geometry over reversible King shuttles."
        ),
        "pressure_definition": (
            "For each player's unretired line containing no opponent piece: +1 per owned node, "
            "+1 per owned pair on that line, +1 if an owned King is present. Candidate value "
            "is own pressure minus opponent pressure times pressure_weight. Terminal scoring is unchanged."
        ),
        "primary_cycle_cases": [
            {
                "case_id": c["id"],
                "clsn": c["clsn"],
                "fingerprint": clsn_fingerprint(parse_clsn(c["clsn"])),
                "moves": list(c["moves"]),
            }
            for c in PRIMARY_D3_CYCLES
        ],
        "legacy_cycle_cases": [
            {
                "case_id": c["id"],
                "clsn": c["clsn"],
                "fingerprint": clsn_fingerprint(parse_clsn(c["clsn"])),
                "moves": list(c["moves"]),
            }
            for c in LEGACY_CYCLES
        ],
        "primary_results": primary,
        "legacy_results": legacy,
        "frozen_suite_results": suite,
        "source_fingerprints": {
            "baseline_ai_sha256": _source_fingerprint("crownline_ai.py"),
            "pressure_engine_sha256": _source_fingerprint("crownline_line_pressure_experiment.py"),
            "experiment_sha256": _source_fingerprint("experiments/benchmark_line_pressure_diagnostic.py"),
            "position_suite_sha256": _source_fingerprint(str(POSITION_SUITE_PATH.relative_to(ROOT))),
        },
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Diagnose Crownline-pressure weighting on frozen cycles.")
    parser.add_argument("--weights", type=float, nargs="+", default=(0, 10, 25, 50, 100, 200))
    parser.add_argument("--depth", type=int, default=3, choices=range(1, 5))
    parser.add_argument("--json", dest="json_path", default=None)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    weights = tuple(float(w) for w in args.weights)
    if 0.0 not in weights:
        raise ValueError("weights must include 0 as the Baseline A control")
    report = run(weights, depth=args.depth)
    print("Crownline Stage 3 Crownline-pressure diagnostic")
    print(f"depth={args.depth} weights={weights}")
    for p, l, s in zip(
        report["primary_results"],
        report["legacy_results"],
        report["frozen_suite_results"],
    ):
        print(
            f"w={p['pressure_weight']:g}: primary cycle {p['cycle_moves_selected']}/12 | "
            f"legacy cycle {l['cycle_moves_selected']}/8 | frozen changes {s['changed_actions']}/16"
        )
    if args.json_path:
        path = Path(args.json_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"JSON report: {path}")


if __name__ == "__main__":
    main()
