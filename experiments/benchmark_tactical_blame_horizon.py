from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Optional

from crownline_ai import _actions
from crownline_rules import Line
from crownline_set import CrownlineSet
from crownline_state_notation import clsn_fingerprint, parse_clsn, serialize_clsn


ROOT = Path(__file__).resolve().parents[1]
WINDOW_PATH = ROOT / "benchmarks" / "human_tactical_blame_windows_v0_1.json"
SCHEMA_VERSION = 1


def _line_tuple(value) -> Optional[Line]:
    return tuple(value) if value else None


def _state(clsn: str, first_game_white: str) -> CrownlineSet:
    return CrownlineSet(
        first_game_white=first_game_white,
        current_game=parse_clsn(clsn),
        rules_mode="candidate",
    )


def _compound_actions(state: CrownlineSet, *, min_legs: int) -> list[tuple[str, Optional[Line], int]]:
    game = state.current_game
    seen: set[tuple[str, str]] = set()
    result = []
    for move, meld_line in _actions(state):
        if len(move.captured) < min_legs:
            continue
        key = (move.notation(), "-".join(meld_line) if meld_line else "")
        if key in seen:
            continue
        seen.add(key)
        points = sum(game.board[square].capture_value() for square in move.captured)
        result.append((move.notation(), meld_line, points))
    return result


def _forced_compound_within(
    state: CrownlineSet,
    protected_participant: str,
    plies_remaining: int,
    *,
    min_legs: int,
    cache: dict[tuple[str, int], bool],
    counter: list[int],
) -> bool:
    """Return whether the opponent can force a compound capture within the horizon.

    The protected participant chooses branches that avoid a compound capture;
    the opponent chooses branches that force one. A compound capture that is
    already legal for the opponent counts immediately and consumes no further
    horizon ply. This is a tactical safety diagnostic, not a game evaluator.
    """

    game = state.current_game
    key = (serialize_clsn(game), plies_remaining)
    cached = cache.get(key)
    if cached is not None:
        return cached
    counter[0] += 1

    if state.set_over or game.game_over:
        cache[key] = False
        return False

    mover = state.participant_for_color(game.turn)
    if mover != protected_participant and _compound_actions(state, min_legs=min_legs):
        cache[key] = True
        return True

    if plies_remaining <= 0:
        cache[key] = False
        return False

    actions = _actions(state)
    if not actions:
        cache[key] = False
        return False

    if mover == protected_participant:
        # The protected player needs only one continuation that avoids the tactic.
        forced = True
        for move, meld_line in actions:
            child = state.apply_move(move, meld_line=meld_line)
            if not _forced_compound_within(
                child,
                protected_participant,
                plies_remaining - 1,
                min_legs=min_legs,
                cache=cache,
                counter=counter,
            ):
                forced = False
                break
    else:
        # The opponent needs only one continuation that forces the tactic.
        forced = False
        for move, meld_line in actions:
            child = state.apply_move(move, meld_line=meld_line)
            if _forced_compound_within(
                child,
                protected_participant,
                plies_remaining - 1,
                min_legs=min_legs,
                cache=cache,
                counter=counter,
            ):
                forced = True
                break

    cache[key] = forced
    return forced


def _action_key(notation: str, meld_line: Optional[Line]) -> tuple[str, str]:
    return notation, "-".join(meld_line) if meld_line else ""


def _analyze_anchor(window: dict[str, Any], anchor: dict[str, Any], *, min_legs: int) -> dict[str, Any]:
    state = _state(anchor["clsn"], window["first_game_white"])
    protected = window["participant"]
    game = state.current_game
    if state.participant_for_color(game.turn) != protected:
        raise ValueError(f"{window['fixture_id']} move {anchor['move_index']}: participant mismatch")
    if clsn_fingerprint(game) != anchor["fingerprint"]:
        raise ValueError(f"{window['fixture_id']} move {anchor['move_index']}: fingerprint mismatch")

    observed_line = _line_tuple(anchor["observed_action"].get("meld_line"))
    observed_key = _action_key(anchor["observed_action"]["notation"], observed_line)
    horizon_after_root = max(0, int(anchor["plies_to_punishment"]) - 1)

    action_results = []
    for move, meld_line in _actions(state):
        child = state.apply_move(move, meld_line=meld_line)
        cache: dict[tuple[str, int], bool] = {}
        counter = [0]
        forced = _forced_compound_within(
            child,
            protected,
            horizon_after_root,
            min_legs=min_legs,
            cache=cache,
            counter=counter,
        )
        action_results.append(
            {
                "notation": move.notation(),
                "meld_line": list(meld_line) if meld_line else None,
                "forced_compound_within_horizon": forced,
                "searched_states": counter[0],
            }
        )

    observed = next(
        item
        for item in action_results
        if _action_key(item["notation"], _line_tuple(item["meld_line"])) == observed_key
    )
    safe = [item for item in action_results if not item["forced_compound_within_horizon"]]
    forcing = [item for item in action_results if item["forced_compound_within_horizon"]]
    return {
        "move_index": anchor["move_index"],
        "plies_to_observed_punishment": anchor["plies_to_punishment"],
        "horizon_after_root": horizon_after_root,
        "root_action_count": len(action_results),
        "observed_action": observed,
        "observed_action_forces_compound_risk": observed["forced_compound_within_horizon"],
        "safe_alternative_count": len(safe),
        "forcing_action_count": len(forcing),
        "blame_candidate": observed["forced_compound_within_horizon"] and bool(safe),
        "safe_alternative_examples": safe[:5],
        "total_searched_states": sum(item["searched_states"] for item in action_results),
    }


def run(*, min_legs: int = 2) -> dict[str, Any]:
    payload = json.loads(WINDOW_PATH.read_text(encoding="utf-8"))
    if payload.get("schema") != "crownline.tactical-blame-windows":
        raise ValueError("Unexpected tactical blame window schema")
    if payload.get("schema_version") != 1:
        raise ValueError("Unsupported tactical blame window schema version")
    if payload.get("rules_mode") != "candidate":
        raise ValueError("Tactical blame windows must use candidate rules")
    if min_legs < 2:
        raise ValueError("min_legs must be at least 2")

    windows = []
    earliest_counts: dict[str, int] = {}
    for window in payload["windows"]:
        anchors = [
            _analyze_anchor(window, anchor, min_legs=min_legs)
            for anchor in window["anchors"]
        ]
        candidates = [anchor for anchor in anchors if anchor["blame_candidate"]]
        earliest = candidates[0] if candidates else None
        if earliest is None:
            classification = "no-avoidable-blame-point-in-window"
        elif earliest["move_index"] == window["target_move_index"]:
            classification = "immediate-move-blame"
        else:
            classification = "upstream-blame"
        earliest_counts[classification] = earliest_counts.get(classification, 0) + 1
        windows.append(
            {
                "fixture_id": window["fixture_id"],
                "source": window["source"],
                "set_sequence": window["set_sequence"],
                "game_number": window["game_number"],
                "participant": window["participant"],
                "target_move_index": window["target_move_index"],
                "punishment": window["punishment"],
                "classification": classification,
                "earliest_blame_move_index": earliest["move_index"] if earliest else None,
                "earliest_blame_plies_before_punishment": (
                    earliest["plies_to_observed_punishment"] if earliest else None
                ),
                "anchors": anchors,
            }
        )

    return {
        "schema_version": SCHEMA_VERSION,
        "experiment": "human-tactical-blame-horizon",
        "suite_id": payload["suite_id"],
        "rules_mode": "candidate",
        "min_capture_legs": min_legs,
        "methodology": {
            "window": "four human decisions ending immediately before each observed compound-capture punishment",
            "horizon": "each anchor is searched only as far as the observed punishment ply",
            "protected_policy": "choose any legal continuation that avoids a compound capture",
            "opponent_policy": "choose any legal continuation that forces a compound capture",
            "interpretation": "horizon-bounded tactical blame diagnostic; not an optimal-play or evaluator claim",
        },
        "summary": {
            "window_count": len(windows),
            "classifications": earliest_counts,
            "upstream_or_immediate_blame_found": sum(
                item["classification"] != "no-avoidable-blame-point-in-window"
                for item in windows
            ),
        },
        "windows": windows,
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Backtrack observed compound-capture mistakes to earlier avoidable human decisions."
    )
    parser.add_argument("--min-legs", type=int, default=2)
    parser.add_argument("--json", dest="json_path", default=None)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    report = run(min_legs=args.min_legs)
    print("Crownline tactical blame-horizon diagnostic")
    print(f"suite={report['suite_id']} windows={report['summary']['window_count']}")
    print(f"classifications={report['summary']['classifications']}")
    for window in report["windows"]:
        print(
            f"{window['fixture_id']}: {window['classification']} | "
            f"earliest={window['earliest_blame_move_index']} | "
            f"punishment={window['punishment']['notation']}"
        )

    if args.json_path:
        destination = Path(args.json_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"JSON report: {destination}")


if __name__ == "__main__":
    main()
