from __future__ import annotations

import argparse
import json
from math import inf
from pathlib import Path

from crownline_ai import _actions, _evaluate, _search, choose_computer_action
from crownline_benchmark import _source_fingerprint
from crownline_rules import opponent
from crownline_set import CrownlineSet
from crownline_state_notation import clsn_fingerprint, parse_clsn, serialize_clsn


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = 1

# Representative exact state preserved by the original Baseline A depth-2
# repetition diagnostic.  The four recorded moves return to this exact state.
CYCLE_START_CLSN = (
    "CLSN1|g=1|r=candidate|t=W|b=6,7|q=-|o=0|e=-|"
    "p=a5:W3,b4:B1K,b6:W6,d4:B3,d6:W5K,g5:B5K,h4:B6|"
    "mw=-|mb=b4.d4.f4:5.3.1:15:0|cw=-|cb=-"
)
CYCLE_MOVES = ("d6-e5", "b4-c3", "e5-d6", "c3-b4")


def _set_for_clsn(clsn: str) -> CrownlineSet:
    game = parse_clsn(clsn)
    return CrownlineSet(
        first_game_white="A",
        current_game=game,
        rules_mode="candidate",
    )


def _action_label(move, meld_line) -> str:
    return move.notation() + (f" | {'-'.join(meld_line)}" if meld_line else "")


def _apply_named_action(state: CrownlineSet, notation: str) -> CrownlineSet:
    matches = [
        (move, meld_line)
        for move, meld_line in _actions(state)
        if move.notation() == notation
    ]
    if len(matches) != 1:
        labels = [_action_label(move, line) for move, line in _actions(state)]
        raise AssertionError(
            f"Expected exactly one {notation!r} action, found {len(matches)}; legal={labels}"
        )
    move, meld_line = matches[0]
    return state.apply_move(move, meld_line=meld_line)


def _static_components(state: CrownlineSet, participant: str) -> dict:
    game = state.current_game
    my_color = state.color_for_participant(participant)
    their_color = opponent(my_color)
    my_score = game.score(my_color).total
    their_score = game.score(their_color).total
    mobility = len(game.legal_moves())
    signed_mobility = (
        mobility
        if state.participant_for_color(game.turn) == participant
        else -mobility
    )
    my_melds = len(game.melds(my_color))
    their_melds = len(game.melds(their_color))
    return {
        "participant": participant,
        "my_color": my_color,
        "my_score": my_score,
        "their_score": their_score,
        "score_margin": my_score - their_score,
        "mobility": mobility,
        "signed_mobility": signed_mobility,
        "my_melds": my_melds,
        "their_melds": their_melds,
        "meld_margin": my_melds - their_melds,
        "static_value": _evaluate(state, participant),
    }


def _action_values(state: CrownlineSet, participant: str, depth: int) -> list[dict]:
    rows = []
    for move, meld_line in _actions(state):
        child = state.apply_move(move, meld_line=meld_line)
        value = _search(child, participant, max(0, depth - 1), -inf, inf)
        rows.append(
            {
                "action": _action_label(move, meld_line),
                "search_value": value,
                "child_fingerprint": clsn_fingerprint(child.current_game),
                "child_static": _static_components(child, participant),
            }
        )
    rows.sort(key=lambda row: (-row["search_value"], row["action"]))
    return rows


def _diagnose_state(state: CrownlineSet, cycle_move: str, depths: tuple[int, ...]) -> dict:
    participant = state.participant_for_color(state.current_game.turn)
    per_depth = []
    for depth in depths:
        notation, meld_line = choose_computer_action(
            state,
            participant=participant,
            depth=depth,
        )
        selected = notation + (f" | {'-'.join(meld_line)}" if meld_line else "")
        rows = _action_values(state, participant, depth)
        best_value = rows[0]["search_value"]
        best_actions = [row["action"] for row in rows if row["search_value"] == best_value]
        selected_row = next(row for row in rows if row["action"] == selected)
        cycle_rows = [row for row in rows if row["action"].split(" | ", 1)[0] == cycle_move]
        cycle_value = cycle_rows[0]["search_value"] if cycle_rows else None
        non_cycle = [row for row in rows if row not in cycle_rows]
        best_non_cycle = max((row["search_value"] for row in non_cycle), default=None)
        per_depth.append(
            {
                "depth": depth,
                "selected_action": selected,
                "selected_is_cycle_move": selected.split(" | ", 1)[0] == cycle_move,
                "selected_value": selected_row["search_value"],
                "best_value": best_value,
                "best_actions": best_actions,
                "best_action_count": len(best_actions),
                "cycle_move": cycle_move,
                "cycle_value": cycle_value,
                "best_non_cycle_value": best_non_cycle,
                "cycle_minus_best_non_cycle": (
                    cycle_value - best_non_cycle
                    if cycle_value is not None and best_non_cycle is not None
                    else None
                ),
                "actions": rows,
            }
        )

    return {
        "clsn": serialize_clsn(state.current_game),
        "fingerprint": clsn_fingerprint(state.current_game),
        "turn": state.current_game.turn,
        "participant": participant,
        "cycle_move": cycle_move,
        "static": _static_components(state, participant),
        "depths": per_depth,
    }


def run(depths: tuple[int, ...]) -> dict:
    start = _set_for_clsn(CYCLE_START_CLSN)
    if serialize_clsn(start.current_game) != CYCLE_START_CLSN:
        raise AssertionError("Representative cycle CLSN is not canonical")

    states = [start]
    cursor = start
    for notation in CYCLE_MOVES:
        cursor = _apply_named_action(cursor, notation)
        states.append(cursor)

    if serialize_clsn(states[-1].current_game) != CYCLE_START_CLSN:
        raise AssertionError("Recorded four-ply trajectory does not return to the exact CLSN state")

    diagnostics = [
        _diagnose_state(states[index], CYCLE_MOVES[index], depths)
        for index in range(4)
    ]

    return {
        "schema_version": SCHEMA_VERSION,
        "experiment": "stage3-cycle-evaluator-diagnostic",
        "rules_mode": "candidate",
        "hypothesis": (
            "Before changing the evaluator, measure whether Baseline A's recorded four-ply "
            "cycle actions are strict minimax preferences or deterministic choices among tied "
            "best actions, and quantify the value gap to the best immediate escape."
        ),
        "cycle_start_clsn": CYCLE_START_CLSN,
        "cycle_start_fingerprint": clsn_fingerprint(start.current_game),
        "cycle_moves": list(CYCLE_MOVES),
        "cycle_round_trip_exact": True,
        "depths": list(depths),
        "states": diagnostics,
        "source_fingerprints": {
            "baseline_ai_sha256": _source_fingerprint("crownline_ai.py"),
            "rules_engine_sha256": _source_fingerprint("crownline_game.py"),
            "clsn_sha256": _source_fingerprint("crownline_state_notation.py"),
            "diagnostic_sha256": _source_fingerprint("experiments/diagnose_stage3_cycle.py"),
            "source_repetition_summary_sha256": _source_fingerprint(
                "benchmarks/baseline_d2_vs_d2_repetition_summary.json"
            ),
        },
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Diagnose Baseline A's preserved four-ply cycle.")
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
    print("Crownline Stage 3 cycle evaluator diagnostic")
    print(f"cycle exact round-trip: {report['cycle_round_trip_exact']}")
    for index, state in enumerate(report["states"], start=1):
        print(f"state {index} {state['turn']} cycle={state['cycle_move']}")
        for depth in state["depths"]:
            print(
                f"  d{depth['depth']}: selected={depth['selected_action']} "
                f"cycle={depth['selected_is_cycle_move']} best_ties={depth['best_action_count']} "
                f"cycle-vs-escape={depth['cycle_minus_best_non_cycle']}"
            )
    if args.json_path:
        path = Path(args.json_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"JSON report: {path}")


if __name__ == "__main__":
    main()
