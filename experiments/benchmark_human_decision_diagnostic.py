from __future__ import annotations

import argparse
import json
from math import inf
from pathlib import Path
from statistics import mean, median
from typing import Any, Optional

from crownline_ai import _actions
from crownline_human_decision_suite import (
    HUMAN_SUITE_ID,
    HUMAN_SUITE_PATH,
    HumanDecisionFixture,
    human_decision_suite,
)
from crownline_promotion_maturity_experiment import _search_promotion_maturity
from crownline_rules import Line, Player, alg_to_coord
from crownline_state_notation import clsn_fingerprint


SCHEMA_VERSION = 1
ROOT = Path(__file__).resolve().parents[1]


def _line_key(line: Optional[Line]) -> str:
    return "-".join(line) if line else ""


def _action_key(notation: str, line: Optional[Line]) -> tuple[str, str]:
    return notation, _line_key(line)


def _capture_exposure(state) -> dict[str, int]:
    """Measure the largest immediately legal reply capture after a root action."""

    game = state.current_game
    if game.game_over:
        return {
            "capture_option_count": 0,
            "max_reply_capture_legs": 0,
            "max_reply_capture_points": 0,
        }

    captures = [move for move in game.legal_moves() if move.is_capture]
    if not captures:
        return {
            "capture_option_count": 0,
            "max_reply_capture_legs": 0,
            "max_reply_capture_points": 0,
        }

    def points(move) -> int:
        return sum(game.board[square].capture_value() for square in move.captured)

    return {
        "capture_option_count": len(captures),
        "max_reply_capture_legs": max(len(move.captured) for move in captures),
        "max_reply_capture_points": max(points(move) for move in captures),
    }


def _geometry_snapshot(game, player: Player) -> dict[str, int]:
    """Return descriptive unretired-line network features, not evaluator weights."""

    retired = game.retired_lines(player)
    cooldowns = game.cooldowns(player)
    unretired = [line for line in game.variant.crown_lines if line not in retired]

    membership_units = 0
    king_membership_units = 0
    occupied_lines = 0
    two_of_three = 0
    king_two_of_three = 0
    ready_king_two_of_three = 0
    three_owned = 0

    for line in unretired:
        pieces = [game.board.get(alg_to_coord(square)) for square in line]
        owned = [piece for piece in pieces if piece is not None and piece.owner == player]
        occupancy = len(owned)
        membership_units += occupancy
        king_membership_units += sum(piece.king for piece in owned)
        occupied_lines += int(occupancy > 0)
        three_owned += int(occupancy == 3)
        if occupancy == 2 and len({piece.value for piece in owned}) == 2:
            two_of_three += 1
            king_supported = any(piece.king for piece in owned)
            king_two_of_three += int(king_supported)
            ready = king_supported and all(cooldowns.get(piece.value, 0) == 0 for piece in owned)
            ready_king_two_of_three += int(ready)

    return {
        "unretired_lines": len(unretired),
        "occupied_unretired_lines": occupied_lines,
        "line_membership_units": membership_units,
        "king_line_membership_units": king_membership_units,
        "two_of_three_lines": two_of_three,
        "king_supported_two_of_three_lines": king_two_of_three,
        "ready_king_supported_two_of_three_lines": ready_king_two_of_three,
        "three_owned_unretired_lines": three_owned,
        "scored_lines": len(game.melds(player)),
        "royal_lines": sum(meld.royal for meld in game.melds(player)),
        "king_piece_count": sum(
            piece.owner == player and piece.king for piece in game.board.values()
        ),
    }


def _rank_actions(
    fixture: HumanDecisionFixture,
    *,
    depth: int,
    maturity_weight: float,
) -> list[dict[str, Any]]:
    state = fixture.state()
    participant = fixture.participant
    player = fixture.color
    before_score = state.current_game.score(player).total
    before_meld_bonus = state.current_game.score(player).meld_bonus

    ranked: list[dict[str, Any]] = []
    for move, meld_line in _actions(state):
        child = state.apply_move(move, meld_line=meld_line)
        value = _search_promotion_maturity(
            child,
            participant,
            max(0, depth - 1),
            -inf,
            inf,
            maturity_weight=maturity_weight,
        )
        after_score = child.current_game.score(player).total
        after_meld_bonus = child.current_game.score(player).meld_bonus
        ranked.append(
            {
                "notation": move.notation(),
                "meld_line": list(meld_line) if meld_line else None,
                "search_value": value,
                "score_delta": after_score - before_score,
                "meld_bonus_delta": after_meld_bonus - before_meld_bonus,
                "capture_exposure": _capture_exposure(child),
                "geometry": _geometry_snapshot(child.current_game, player),
                "after_fingerprint": clsn_fingerprint(child.current_game),
            }
        )

    ranked.sort(
        key=lambda item: (
            -item["search_value"],
            item["notation"],
            "-".join(item["meld_line"] or []),
        )
    )
    for rank, item in enumerate(ranked, start=1):
        item["rank"] = rank
        item["value_gap_from_best"] = ranked[0]["search_value"] - item["search_value"]
    return ranked


def _fixture_report(
    fixture: HumanDecisionFixture,
    *,
    depth: int,
    maturity_weight: float,
) -> dict[str, Any]:
    ranked = _rank_actions(
        fixture,
        depth=depth,
        maturity_weight=maturity_weight,
    )
    observed_key = _action_key(
        fixture.observed_action.notation,
        fixture.observed_action.meld_line,
    )
    observed = next(
        item
        for item in ranked
        if _action_key(
            item["notation"],
            tuple(item["meld_line"]) if item["meld_line"] else None,
        )
        == observed_key
    )
    best = ranked[0]

    exposure_order = sorted(
        ranked,
        key=lambda item: (
            item["capture_exposure"]["max_reply_capture_legs"],
            item["capture_exposure"]["max_reply_capture_points"],
            item["capture_exposure"]["capture_option_count"],
            item["notation"],
            "-".join(item["meld_line"] or []),
        ),
    )
    safest = exposure_order[0]

    geometry_keys = (
        "occupied_unretired_lines",
        "line_membership_units",
        "king_line_membership_units",
        "two_of_three_lines",
        "king_supported_two_of_three_lines",
        "ready_king_supported_two_of_three_lines",
        "three_owned_unretired_lines",
    )
    geometry_delta = {
        key: observed["geometry"][key] - best["geometry"][key]
        for key in geometry_keys
    }

    return {
        "fixture_id": fixture.fixture_id,
        "bucket": fixture.bucket,
        "source": fixture.source,
        "set_sequence": fixture.set_sequence,
        "game_number": fixture.game_number,
        "move_index": fixture.move_index,
        "participant": fixture.participant,
        "color": fixture.color,
        "controller": fixture.controller,
        "clsn": fixture.clsn,
        "fingerprint": fixture.fingerprint,
        "annotation": fixture.annotation,
        "root_action_count": len(ranked),
        "observed_action": observed,
        "ai_best_action": best,
        "observed_matches_ai_best": observed["rank"] == 1,
        "safest_immediate_capture_action": safest,
        "observed_is_safest_immediate_capture_action": (
            observed["capture_exposure"]["max_reply_capture_legs"],
            observed["capture_exposure"]["max_reply_capture_points"],
            observed["capture_exposure"]["capture_option_count"],
        )
        == (
            safest["capture_exposure"]["max_reply_capture_legs"],
            safest["capture_exposure"]["max_reply_capture_points"],
            safest["capture_exposure"]["capture_option_count"],
        ),
        "observed_geometry_minus_ai_best": geometry_delta,
        "top_actions": ranked[: min(5, len(ranked))],
    }


def _bucket_summary(records: list[dict[str, Any]]) -> dict[str, Any]:
    ranks = [record["observed_action"]["rank"] for record in records]
    summary: dict[str, Any] = {
        "fixture_count": len(records),
        "observed_matches_ai_best": sum(record["observed_matches_ai_best"] for record in records),
        "observed_top3": sum(record["observed_action"]["rank"] <= 3 for record in records),
        "mean_observed_rank": mean(ranks),
        "median_observed_rank": median(ranks),
        "mean_root_action_count": mean(record["root_action_count"] for record in records),
    }

    if records and records[0]["bucket"] == "human-tactical-error":
        summary["observed_safest_immediate_capture"] = sum(
            record["observed_is_safest_immediate_capture_action"] for record in records
        )
        summary["recognized_errors_with_safer_legal_action"] = sum(
            not record["observed_is_safest_immediate_capture_action"] for record in records
        )
        summary["mean_observed_max_reply_capture_points"] = mean(
            record["observed_action"]["capture_exposure"]["max_reply_capture_points"]
            for record in records
        )
        summary["mean_safest_max_reply_capture_points"] = mean(
            record["safest_immediate_capture_action"]["capture_exposure"]["max_reply_capture_points"]
            for record in records
        )

    geometry_keys = records[0]["observed_geometry_minus_ai_best"].keys() if records else ()
    summary["mean_observed_geometry_minus_ai_best"] = {
        key: mean(record["observed_geometry_minus_ai_best"][key] for record in records)
        for key in geometry_keys
    }
    return summary


def _sha256(path: Path) -> str:
    import hashlib

    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(*, depth: int = 3, maturity_weight: float = 10.0) -> dict[str, Any]:
    if depth < 1 or depth > 4:
        raise ValueError("depth must be between 1 and 4")
    if maturity_weight < 0:
        raise ValueError("maturity_weight must be non-negative")

    fixtures = human_decision_suite()
    records = [
        _fixture_report(
            fixture,
            depth=depth,
            maturity_weight=maturity_weight,
        )
        for fixture in fixtures
    ]
    buckets: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        buckets.setdefault(record["bucket"], []).append(record)

    return {
        "schema_version": SCHEMA_VERSION,
        "experiment": "human-decision-diagnostic",
        "suite_id": HUMAN_SUITE_ID,
        "rules_mode": "candidate",
        "depth": depth,
        "maturity_weight": maturity_weight,
        "methodology": {
            "search": "deterministic fixed-depth alpha-beta with promotion maturity; no repeat-history policy",
            "observed_moves_are_labels": False,
            "capture_exposure": "largest immediately legal reply capture after each root action",
            "geometry_features": "descriptive unretired-line network proxies only; no evaluator weights changed",
        },
        "source_fingerprints": {
            "suite_manifest_sha256": _sha256(HUMAN_SUITE_PATH),
            "tactical_fixtures_sha256": _sha256(ROOT / "benchmarks" / "human_decision_tactical_v0_1.json"),
            "bot_build_fixtures_sha256": _sha256(ROOT / "benchmarks" / "human_decision_bot_build_v0_1.json"),
            "royal_sweep_fixtures_sha256": _sha256(ROOT / "benchmarks" / "human_decision_royal_sweep_v0_1.json"),
        },
        "summary": {
            "fixture_count": len(records),
            "bucket_counts": {bucket: len(items) for bucket, items in buckets.items()},
            "buckets": {bucket: _bucket_summary(items) for bucket, items in buckets.items()},
        },
        "fixtures": records,
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compare frozen human/browser decisions with the current fixed-depth Crownline evaluator."
    )
    parser.add_argument("--depth", type=int, default=3, choices=range(1, 5))
    parser.add_argument("--maturity-weight", type=float, default=10.0)
    parser.add_argument("--json", dest="json_path", default=None)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    report = run(depth=args.depth, maturity_weight=args.maturity_weight)
    print("Crownline human-decision diagnostic")
    print(
        f"suite={report['suite_id']} fixtures={report['summary']['fixture_count']} "
        f"depth={report['depth']} maturity={report['maturity_weight']:g}"
    )
    for bucket, summary in report["summary"]["buckets"].items():
        print(
            f"{bucket}: n={summary['fixture_count']} | "
            f"AI-best matches={summary['observed_matches_ai_best']} | "
            f"top3={summary['observed_top3']} | "
            f"median rank={summary['median_observed_rank']}"
        )
        if bucket == "human-tactical-error":
            print(
                "  safer immediate action existed: "
                f"{summary['recognized_errors_with_safer_legal_action']}/{summary['fixture_count']}"
            )

    if args.json_path:
        destination = Path(args.json_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(f"JSON report: {destination}")


if __name__ == "__main__":
    main()
