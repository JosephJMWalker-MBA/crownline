from __future__ import annotations

import argparse
import json
from math import inf
from pathlib import Path

from crownline_ai import _actions, _search
from crownline_benchmark import _source_fingerprint
from crownline_king_position_suite import (
    KING_POSITION_SUITE_PATH,
    king_position_suite,
)
from crownline_position_suite import POSITION_SUITE_PATH, position_suite
from crownline_rules import coord_to_alg, opponent
from crownline_set import CrownlineSet
from crownline_state_notation import serialize_clsn
from experiments.diagnose_stage3_cycle import (
    CYCLE_MOVES,
    CYCLE_START_CLSN,
    _apply_named_action,
    _set_for_clsn,
)


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = 2


def _king_features(game, player: str) -> dict:
    kings = [
        (position, piece)
        for position, piece in game.board.items()
        if piece.owner == player and piece.king
    ]
    normals = [
        (position, piece)
        for position, piece in game.board.items()
        if piece.owner == player and not piece.king
    ]

    king_step_options = 0
    king_backward_steps = 0
    king_capture_paths = 0
    king_board_value = 0
    king_crownline_incidence = 0
    backward_dr = -1 if player == "W" else 1
    retired = game.retired_lines(player)

    for position, piece in kings:
        king_board_value += game.variant.square_value(position)
        square = coord_to_alg(position)
        king_crownline_incidence += sum(
            square in line and line not in retired
            for line in game.variant.crown_lines
        )
        f, r = position
        for df, dr in game._dirs(piece):
            destination = (f + df, r + dr)
            if game.variant.playable(destination) and destination not in game.board:
                king_step_options += 1
                if dr == backward_dr:
                    king_backward_steps += 1
        king_capture_paths += len(
            game._capture_sequences_from(game.board, position, piece)
        )

    # Immediate King liability is measured from the opponent's raw capture
    # geometry, independent of whose turn it currently is. A King is counted at
    # most once even when multiple capture sequences can take it.
    endangered = set()
    threat_paths = 0
    enemy = opponent(player)
    for position, piece in game.board.items():
        if piece.owner != enemy:
            continue
        for move in game._capture_sequences_from(game.board, position, piece):
            captured_kings = [
                square
                for square in move.captured
                if (victim := game.board.get(square)) is not None
                and victim.owner == player
                and victim.king
            ]
            if captured_kings:
                threat_paths += 1
                endangered.update(captured_kings)
    king_capture_liability = sum(
        game.board[square].capture_value() for square in endangered
    )

    # Promotion progress is reported rather than immediately valued. A normal
    # White piece has seven rank steps from rank 1 to rank 8; Black is mirrored.
    progress_units = 0
    proximity_units = 0.0
    min_distance = None
    for (_, r), piece in normals:
        distance = 8 - r if player == "W" else r - 1
        progress = 7 - distance
        progress_units += progress
        proximity_units += 1.0 / max(1, distance)
        min_distance = distance if min_distance is None else min(min_distance, distance)

    return {
        "king_count": len(kings),
        "king_board_value": king_board_value,
        "king_step_options": king_step_options,
        "king_backward_steps": king_backward_steps,
        "king_capture_paths": king_capture_paths,
        "king_unretired_line_incidence": king_crownline_incidence,
        "king_capture_liability": king_capture_liability,
        "king_threat_paths": threat_paths,
        "normal_count": len(normals),
        "promotion_progress_units": progress_units,
        "promotion_proximity_units": proximity_units,
        "minimum_promotion_distance": min_distance,
    }


def _feature_snapshot(state: CrownlineSet, participant: str) -> dict:
    game = state.current_game
    my_color = state.color_for_participant(participant)
    their_color = opponent(my_color)
    mine = _king_features(game, my_color)
    theirs = _king_features(game, their_color)
    signed_keys = (
        "king_count",
        "king_board_value",
        "king_step_options",
        "king_backward_steps",
        "king_capture_paths",
        "king_unretired_line_incidence",
        "normal_count",
        "promotion_progress_units",
        "promotion_proximity_units",
    )
    margins = {key: mine[key] - theirs[key] for key in signed_keys}
    # Liability is bad for the owner, so the participant-favorable margin is
    # opponent liability minus own liability.
    margins["king_safety"] = (
        theirs["king_capture_liability"] - mine["king_capture_liability"]
    )
    margins["king_threat_path_safety"] = (
        theirs["king_threat_paths"] - mine["king_threat_paths"]
    )
    return {
        "participant": participant,
        "my_color": my_color,
        "mine": mine,
        "theirs": theirs,
        "margins": margins,
    }


def _action_row(
    state: CrownlineSet,
    participant: str,
    move,
    meld_line,
    depth: int,
) -> dict:
    child = state.apply_move(move, meld_line=meld_line)
    value = _search(child, participant, max(0, depth - 1), -inf, inf)
    return {
        "action": move.notation()
        + (f" | {'-'.join(meld_line)}" if meld_line else ""),
        "search_value": value,
        "features": _feature_snapshot(child, participant),
        "child_clsn": serialize_clsn(child.current_game),
    }


def _cycle_diagnostic(depth: int) -> list[dict]:
    states = []
    cursor = _set_for_clsn(CYCLE_START_CLSN)
    for notation in CYCLE_MOVES:
        states.append(cursor)
        cursor = _apply_named_action(cursor, notation)

    output = []
    for state, cycle_move in zip(states, CYCLE_MOVES):
        participant = state.participant_for_color(state.current_game.turn)
        rows = [
            _action_row(state, participant, move, meld_line, depth)
            for move, meld_line in _actions(state)
        ]
        rows.sort(key=lambda row: (-row["search_value"], row["action"]))
        cycle = next(
            row
            for row in rows
            if row["action"].split(" | ", 1)[0] == cycle_move
        )
        escape = next(
            row
            for row in rows
            if row["action"].split(" | ", 1)[0] != cycle_move
        )
        keys = cycle["features"]["margins"].keys()
        feature_delta_cycle_minus_escape = {
            key: (
                cycle["features"]["margins"][key]
                - escape["features"]["margins"][key]
            )
            for key in keys
        }
        output.append(
            {
                "turn": state.current_game.turn,
                "participant": participant,
                "state_clsn": serialize_clsn(state.current_game),
                "state_features": _feature_snapshot(state, participant),
                "cycle_move": cycle_move,
                "cycle": cycle,
                "best_non_cycle": escape,
                "cycle_minus_escape_search_value": (
                    cycle["search_value"] - escape["search_value"]
                ),
                "feature_delta_cycle_minus_escape": (
                    feature_delta_cycle_minus_escape
                ),
            }
        )
    return output


def _summarize_margin_samples(samples_by_key: dict[str, list[float]]) -> dict:
    return {
        key: {
            "min": min(samples),
            "max": max(samples),
            "distinct": len(set(samples)),
            "nonzero_observations": sum(value != 0 for value in samples),
        }
        for key, samples in samples_by_key.items()
    }


def _early_feature_ranges() -> dict:
    """Retain the original frozen suite as an explicit early-game control."""
    samples_by_key: dict[str, list[float]] = {}
    observations = 0
    king_positions = 0
    for scenario in position_suite():
        for fixture in (scenario.game1, scenario.game2):
            game = fixture.game()
            king_positions += int(any(piece.king for piece in game.board.values()))
            state = CrownlineSet(
                first_game_white="A",
                current_game=game,
                rules_mode="candidate",
            )
            for participant in ("A", "B"):
                margins = _feature_snapshot(state, participant)["margins"]
                for key, value in margins.items():
                    samples_by_key.setdefault(key, []).append(value)
                observations += 1
    return {
        "suite": "v0.1",
        "positions": 16,
        "observations": observations,
        "positions_containing_kings": king_positions,
        "ranges": _summarize_margin_samples(samples_by_key),
    }


def _king_hard_case_feature_ranges() -> dict:
    """Measure feature variation on the artifact-derived King-rich guardrail."""
    samples_by_key: dict[str, list[float]] = {}
    observations = 0
    king_counts = []
    cycle_lengths = set()
    game_numbers = set()
    for fixture in king_position_suite():
        game = fixture.game()
        king_counts.append(sum(piece.king for piece in game.board.values()))
        cycle_lengths.add(fixture.cycle_length)
        game_numbers.add(game.variant.number)
        state = CrownlineSet(
            first_game_white="A",
            current_game=game,
            rules_mode="candidate",
        )
        for participant in ("A", "B"):
            margins = _feature_snapshot(state, participant)["margins"]
            for key, value in margins.items():
                samples_by_key.setdefault(key, []).append(value)
            observations += 1
    return {
        "suite": "king-v0.1",
        "positions": len(king_counts),
        "observations": observations,
        "king_count_range": [min(king_counts), max(king_counts)],
        "cycle_lengths": sorted(cycle_lengths),
        "game_numbers": sorted(game_numbers),
        "ranges": _summarize_margin_samples(samples_by_key),
    }


def run(depth: int) -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "experiment": "stage3-king-utility-feature-diagnostic",
        "rules_mode": "candidate",
        "depth": depth,
        "hypothesis": (
            "Before assigning any King or promotion bonus, decompose position-sensitive King "
            "utility and promotion potential and measure which components actually distinguish "
            "the preserved cycle move from its best immediate escape."
        ),
        "feature_notes": {
            "king_step_options": (
                "empty adjacent diagonals available to existing Kings, independent of turn obligation"
            ),
            "king_backward_steps": (
                "subset of King step options unavailable to an otherwise equivalent ordinary piece"
            ),
            "king_capture_paths": (
                "complete immediate capture sequences available geometrically to existing Kings"
            ),
            "king_unretired_line_incidence": (
                "unretired Crownline geometries containing squares currently occupied by Kings"
            ),
            "king_safety": (
                "opponent immediately-capturable King value minus own immediately-capturable King value"
            ),
            "promotion_progress_units": (
                "mirrored rank progress of ordinary pieces toward promotion"
            ),
            "promotion_proximity_units": (
                "sum of reciprocal remaining promotion distance for ordinary pieces"
            ),
        },
        "cycle_states": _cycle_diagnostic(depth),
        "early_control_feature_ranges": _early_feature_ranges(),
        "king_hard_case_feature_ranges": _king_hard_case_feature_ranges(),
        "source_fingerprints": {
            "baseline_ai_sha256": _source_fingerprint("crownline_ai.py"),
            "rules_engine_sha256": _source_fingerprint("crownline_game.py"),
            "cycle_diagnostic_sha256": _source_fingerprint(
                "experiments/diagnose_stage3_cycle.py"
            ),
            "early_position_suite_sha256": _source_fingerprint(
                str(POSITION_SUITE_PATH.relative_to(ROOT))
            ),
            "king_position_suite_sha256": _source_fingerprint(
                str(KING_POSITION_SUITE_PATH.relative_to(ROOT))
            ),
            "king_position_loader_sha256": _source_fingerprint(
                "crownline_king_position_suite.py"
            ),
            "king_utility_diagnostic_sha256": _source_fingerprint(
                "experiments/diagnose_king_utility.py"
            ),
        },
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Diagnose transparent King/promotion utility features on preserved Crownline cycle states."
        )
    )
    parser.add_argument("--depth", type=int, default=2, choices=range(1, 5))
    parser.add_argument("--json", dest="json_path", default=None)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    report = run(args.depth)
    print("Crownline Stage 3 King-utility feature diagnostic")
    print(f"depth={report['depth']}")
    for index, row in enumerate(report["cycle_states"], start=1):
        print(
            f"state {index} {row['turn']}: cycle {row['cycle_move']} vs "
            f"{row['best_non_cycle']['action']} | search gap "
            f"{row['cycle_minus_escape_search_value']}"
        )
        deltas = row["feature_delta_cycle_minus_escape"]
        print(
            "  feature delta cycle-escape: "
            + ", ".join(
                f"{key}={value}" for key, value in deltas.items() if value != 0
            )
        )

    early = report["early_control_feature_ranges"]
    print(
        f"Early control: {early['positions']} positions | "
        f"King positions {early['positions_containing_kings']}"
    )
    hard = report["king_hard_case_feature_ranges"]
    print(
        f"King hard cases: {hard['positions']} positions | Kings "
        f"{hard['king_count_range'][0]}..{hard['king_count_range'][1]} | "
        f"games {hard['game_numbers']} | cycles {hard['cycle_lengths']}"
    )
    for key, stats in hard["ranges"].items():
        print(
            f"  {key}: {stats['min']}..{stats['max']} "
            f"({stats['distinct']} distinct; {stats['nonzero_observations']} nonzero)"
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
