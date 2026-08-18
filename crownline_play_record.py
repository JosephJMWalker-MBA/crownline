from __future__ import annotations

from copy import deepcopy
from typing import Any, Optional

from crownline_game import Line, Move
from crownline_set import CrownlineSet
from crownline_state_notation import clsn_fingerprint, serialize_clsn


PLAY_RECORD_SCHEMA = "crownline.play-record"
PLAY_RECORD_SCHEMA_VERSION = 1


def _meld_dict(meld) -> dict[str, Any]:
    return {
        "line": list(meld.line),
        "piece_ids": list(meld.piece_ids),
        "points": meld.points,
        "royal": meld.royal,
    }


def _score_snapshot(crownline_set: CrownlineSet) -> dict[str, Any]:
    game = crownline_set.current_game
    score_w = game.score("W")
    score_b = game.score("B")
    return {
        "W": {
            "capture": score_w.capture_bank,
            "board": score_w.board_value,
            "melds": score_w.meld_count,
            "meld_bonus": score_w.meld_bonus,
            "total": score_w.total,
        },
        "B": {
            "capture": score_b.capture_bank,
            "board": score_b.board_value,
            "melds": score_b.meld_count,
            "meld_bonus": score_b.meld_bonus,
            "total": score_b.total,
        },
    }


def _game_record(crownline_set: CrownlineSet) -> dict[str, Any]:
    game = crownline_set.current_game
    return {
        "game_number": game.variant.number,
        "white_participant": crownline_set.white_participant,
        "black_participant": crownline_set.black_participant,
        "initial_clsn": serialize_clsn(game),
        "initial_fingerprint": clsn_fingerprint(game),
        "moves": [],
        "result": None,
    }


def _set_record(crownline_set: CrownlineSet, *, sequence: int, opened_reason: str) -> dict[str, Any]:
    return {
        "sequence": sequence,
        "set_index": crownline_set.set_index,
        "rules_mode": crownline_set.rules_mode,
        "first_game_white": crownline_set.first_game_white,
        "carry_score_a": crownline_set.carry_score_a,
        "carry_score_b": crownline_set.carry_score_b,
        "opened_reason": opened_reason,
        "closed_reason": None,
        "games": [_game_record(crownline_set)],
        "result": None,
    }


def new_play_record(crownline_set: CrownlineSet) -> dict[str, Any]:
    """Create an append-only browser-session record suitable for later analysis.

    CLSN is stored before and after every move. That makes each human decision a
    reconstructible training/evaluation example without duplicating legal-action
    generation in the export format: legal alternatives can be regenerated from
    `before_clsn` by the authoritative rules engine.
    """

    return {
        "schema": PLAY_RECORD_SCHEMA,
        "schema_version": PLAY_RECORD_SCHEMA_VERSION,
        "sets": [_set_record(crownline_set, sequence=1, opened_reason="server_start")],
    }


def _current_set_record(record: dict[str, Any]) -> dict[str, Any]:
    sets = record.get("sets") or []
    if not sets:
        raise ValueError("Play record has no active set")
    return sets[-1]


def _current_game_record(record: dict[str, Any], crownline_set: CrownlineSet) -> dict[str, Any]:
    set_record = _current_set_record(record)
    games = set_record.get("games") or []
    if not games:
        raise ValueError("Play record has no active game")
    game_record = games[-1]
    if game_record["game_number"] != crownline_set.game_number:
        raise ValueError("Play record game does not match Crownline state")
    return game_record


def _promotion_ids(before, after, player: str) -> list[int]:
    before_by_identity = {
        (piece.owner, piece.value): piece
        for piece in before.board.values()
    }
    after_by_identity = {
        (piece.owner, piece.value): piece
        for piece in after.board.values()
    }
    promoted = []
    for identity, before_piece in before_by_identity.items():
        owner, piece_id = identity
        after_piece = after_by_identity.get(identity)
        if (
            owner == player
            and after_piece is not None
            and not before_piece.king
            and after_piece.king
        ):
            promoted.append(piece_id)
    return sorted(promoted)


def _capture_bank(game, player: str) -> int:
    return game.capture_bank_w if player == "W" else game.capture_bank_b


def record_move(
    record: dict[str, Any],
    before_set: CrownlineSet,
    after_set: CrownlineSet,
    move: Move,
    *,
    meld_line: Optional[Line],
    controller: str,
    ai_evidence: Optional[dict[str, Any]] = None,
) -> None:
    """Append one authoritative move example to the active game record."""

    if controller not in ("human", "computer"):
        raise ValueError("controller must be 'human' or 'computer'")
    before = before_set.current_game
    after = after_set.current_game
    if before.variant.number != after.variant.number:
        raise ValueError("A recorded move cannot cross game variants")

    player = before.turn
    participant = before_set.participant_for_color(player)
    before_melds = before.melds(player)
    after_melds = after.melds(player)
    new_melds = after_melds[len(before_melds):]

    event = {
        "move_index": len(_current_game_record(record, before_set)["moves"]) + 1,
        "ply_before": before.ply,
        "ply_after": after.ply,
        "participant": participant,
        "color": player,
        "controller": controller,
        "notation": move.notation(),
        "meld_line": list(meld_line) if meld_line else None,
        "before_clsn": serialize_clsn(before),
        "before_fingerprint": clsn_fingerprint(before),
        "after_clsn": serialize_clsn(after),
        "after_fingerprint": clsn_fingerprint(after),
        "capture_delta": _capture_bank(after, player) - _capture_bank(before, player),
        "promoted_piece_ids": _promotion_ids(before, after, player),
        "crownlines_scored": [_meld_dict(meld) for meld in new_melds],
        "triggering_player_after": after.triggering_player,
        "game_over_after": after.game_over,
        "end_reason_after": after.end_reason,
        "score_after": _score_snapshot(after_set),
        "ai": deepcopy(ai_evidence) if ai_evidence else None,
    }
    _current_game_record(record, before_set)["moves"].append(event)
    if after.game_over:
        finalize_current_game(record, after_set)


def _game_result(crownline_set: CrownlineSet) -> dict[str, Any]:
    game = crownline_set.current_game
    score_w = game.score("W").total
    score_b = game.score("B").total
    if crownline_set.white_participant == "A":
        score_a, score_b = score_w, score_b
    else:
        score_a, score_b = score_b, score_w
    winner = "A" if score_a > score_b else "B" if score_b > score_a else "DRAW"
    return {
        "game_number": game.variant.number,
        "score_a": score_a,
        "score_b": score_b,
        "white_score": score_w,
        "black_score": score_b if crownline_set.white_participant == "A" else score_a,
        "winner": winner,
        "end_reason": game.end_reason,
        "final_clsn": serialize_clsn(game),
        "final_fingerprint": clsn_fingerprint(game),
    }


def finalize_current_game(record: dict[str, Any], crownline_set: CrownlineSet) -> None:
    game = crownline_set.current_game
    if not game.game_over:
        return
    game_record = _current_game_record(record, crownline_set)
    if game_record["result"] is None:
        game_record["result"] = _game_result(crownline_set)


def record_advance(
    record: dict[str, Any],
    before_set: CrownlineSet,
    after_set: CrownlineSet,
) -> None:
    """Record Game 1 -> Game 2 or Game 2 -> completed-set transitions."""

    finalize_current_game(record, before_set)
    set_record = _current_set_record(record)
    if before_set.game_number == 1 and after_set.game_number == 2:
        set_record["games"].append(_game_record(after_set))
    if after_set.set_over:
        score_a, score_b = after_set.aggregate_scores()
        set_record["result"] = {
            "aggregate_a": score_a,
            "aggregate_b": score_b,
            "winner": after_set.winner(),
        }
        set_record["closed_reason"] = "completed"


def record_new_set(
    record: dict[str, Any],
    crownline_set: CrownlineSet,
    *,
    opened_reason: str,
) -> None:
    """Keep earlier games when the browser resets or continues a tied set."""

    current = _current_set_record(record)
    if current["closed_reason"] is None:
        current["closed_reason"] = "reset" if opened_reason == "reset" else "continued"
    record["sets"].append(
        _set_record(
            crownline_set,
            sequence=len(record["sets"]) + 1,
            opened_reason=opened_reason,
        )
    )


def export_play_record(record: dict[str, Any], crownline_set: CrownlineSet) -> dict[str, Any]:
    """Return a detached JSON-safe snapshot plus useful live-session summary."""

    payload = deepcopy(record)
    sets = payload["sets"]
    games = [game for set_record in sets for game in set_record["games"]]
    moves = [move for game in games for move in game["moves"]]
    aggregate_a, aggregate_b = crownline_set.aggregate_scores()
    payload["summary"] = {
        "sets_recorded": len(sets),
        "games_recorded": len(games),
        "moves_recorded": len(moves),
        "human_moves_recorded": sum(move["controller"] == "human" for move in moves),
        "computer_moves_recorded": sum(move["controller"] == "computer" for move in moves),
        "current_rules_mode": crownline_set.rules_mode,
        "current_set_index": crownline_set.set_index,
        "current_game_number": crownline_set.game_number,
        "current_set_over": crownline_set.set_over,
        "current_aggregate": {"A": aggregate_a, "B": aggregate_b},
    }
    return payload
