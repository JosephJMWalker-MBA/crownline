from __future__ import annotations

import hashlib
import re
from typing import Dict, Iterable, Tuple

from crownline_game import GameState, Meld, Piece
from crownline_rules import (
    MELD_BONUS,
    MELD_COOLDOWN_TURNS,
    ROYAL_MELD_BONUS,
    Line,
    Player,
    alg_to_coord,
    coord_to_alg,
    normalize_rules_mode,
    uses_crowned_meld,
    variant_for,
)


CLSN_VERSION = "CLSN1"
_FIELD_ORDER = ("g", "r", "t", "b", "q", "o", "e", "p", "mw", "mb", "cw", "cb")
_PIECE_RE = re.compile(r"^(W|B)([1-6])(K?)$")
_END_REASON_RE = re.compile(r"^[a-z0-9_]+$")


def _parse_nonnegative_int(text: str, *, label: str) -> int:
    try:
        value = int(text)
    except ValueError as exc:
        raise ValueError(f"{label} must be an integer") from exc
    if value < 0:
        raise ValueError(f"{label} must be non-negative")
    return value


def _piece_text(piece: Piece) -> str:
    return f"{piece.owner}{piece.value}{'K' if piece.king else ''}"


def _parse_board(text: str, *, game_number: int) -> Dict[tuple[int, int], Piece]:
    if text == "-":
        return {}

    variant = variant_for(game_number)
    board: Dict[tuple[int, int], Piece] = {}
    identities: set[tuple[Player, int]] = set()
    for token in text.split(","):
        try:
            square, piece_text = token.split(":", 1)
        except ValueError as exc:
            raise ValueError(f"Invalid board token {token!r}") from exc
        coord = alg_to_coord(square)
        if not variant.playable(coord):
            raise ValueError(f"Square {square!r} is not playable in Game {game_number}")
        if coord in board:
            raise ValueError(f"Duplicate board square {square!r}")
        match = _PIECE_RE.fullmatch(piece_text)
        if match is None:
            raise ValueError(f"Invalid piece token {piece_text!r}")
        owner = match.group(1)
        value = int(match.group(2))
        identity = (owner, value)
        if identity in identities:
            raise ValueError(f"Duplicate piece identity {owner}{value}")
        identities.add(identity)
        board[coord] = Piece(owner, value, king=bool(match.group(3)))
    return board


def _meld_text(meld: Meld) -> str:
    return (
        f"{'.'.join(meld.line)}:"
        f"{'.'.join(str(piece_id) for piece_id in meld.piece_ids)}:"
        f"{meld.points}:{1 if meld.royal else 0}"
    )


def _parse_melds(text: str, *, game_number: int, rules_mode: str) -> Tuple[Meld, ...]:
    if text == "-":
        return ()

    variant = variant_for(game_number)
    melds = []
    for token in text.split(","):
        parts = token.split(":")
        if len(parts) != 4:
            raise ValueError(f"Invalid meld token {token!r}")
        line_text, ids_text, points_text, royal_text = parts
        squares = tuple(line_text.split("."))
        if len(squares) != 3:
            raise ValueError("A Crownline meld must contain exactly three squares")
        for square in squares:
            alg_to_coord(square)
        line: Line = squares  # type: ignore[assignment]
        if line not in variant.crown_lines:
            raise ValueError(f"{line_text!r} is not a Game {game_number} Crownline")

        try:
            piece_ids = tuple(int(value) for value in ids_text.split("."))
        except ValueError as exc:
            raise ValueError(f"Invalid meld identities {ids_text!r}") from exc
        if len(piece_ids) != 3 or any(piece_id not in range(1, 7) for piece_id in piece_ids):
            raise ValueError("Meld identities must contain three values from 1 through 6")
        if len(set(piece_ids)) != 3:
            raise ValueError("Meld identities must be distinct")

        points = _parse_nonnegative_int(points_text, label="meld points")
        if royal_text not in ("0", "1"):
            raise ValueError("Royal flag must be 0 or 1")
        royal = royal_text == "1"
        expected_points = ROYAL_MELD_BONUS if royal else MELD_BONUS
        if points != expected_points:
            raise ValueError(
                f"Meld points must be {expected_points} when royal={int(royal)}"
            )
        if royal and not uses_crowned_meld(normalize_rules_mode(rules_mode)):
            raise ValueError("Royal Crownlines are not valid in this rules mode")
        melds.append(Meld(line=line, piece_ids=piece_ids, points=points, royal=royal))

    return tuple(
        sorted(
            melds,
            key=lambda meld: (meld.line, meld.piece_ids, meld.points, meld.royal),
        )
    )


def _cooldown_text(cooldowns: Iterable[tuple[int, int]]) -> str:
    packed = tuple(sorted(cooldowns))
    if not packed:
        return "-"
    return ",".join(f"{piece_id}:{turns}" for piece_id, turns in packed)


def _parse_cooldowns(text: str, *, rules_mode: str) -> Tuple[tuple[int, int], ...]:
    if text == "-":
        return ()
    if not uses_crowned_meld(normalize_rules_mode(rules_mode)):
        raise ValueError("Cooldowns are not valid in this rules mode")

    cooldowns: dict[int, int] = {}
    for token in text.split(","):
        try:
            piece_id_text, turns_text = token.split(":", 1)
            piece_id = int(piece_id_text)
            turns = int(turns_text)
        except ValueError as exc:
            raise ValueError(f"Invalid cooldown token {token!r}") from exc
        if piece_id not in range(1, 7):
            raise ValueError("Cooldown piece identity must be between 1 and 6")
        if turns not in range(1, MELD_COOLDOWN_TURNS + 1):
            raise ValueError(
                f"Cooldown turns must be between 1 and {MELD_COOLDOWN_TURNS}"
            )
        if piece_id in cooldowns:
            raise ValueError(f"Duplicate cooldown identity {piece_id}")
        cooldowns[piece_id] = turns
    return tuple(sorted(cooldowns.items()))


def _validate_state(state: GameState) -> None:
    if state.variant.number not in (1, 2):
        raise ValueError("CLSN supports Crownline Game 1 or Game 2 only")
    normalize_rules_mode(state.rules_mode)
    if state.turn not in ("W", "B"):
        raise ValueError("turn must be W or B")
    if state.capture_bank_w < 0 or state.capture_bank_b < 0:
        raise ValueError("capture banks must be non-negative")
    if state.triggering_player not in (None, "W", "B"):
        raise ValueError("triggering_player must be W, B, or None")
    if state.game_over != (state.end_reason is not None):
        raise ValueError("game_over and end_reason must agree")
    if state.end_reason is not None and _END_REASON_RE.fullmatch(state.end_reason) is None:
        raise ValueError("end_reason contains characters CLSN1 cannot encode")

    # Reuse the parser validators so manually constructed GameStates cannot be
    # serialized into an invalid canonical position.
    board_text = ",".join(
        f"{coord_to_alg(position)}:{_piece_text(piece)}"
        for position, piece in sorted(
            state.board.items(), key=lambda item: coord_to_alg(item[0])
        )
    ) or "-"
    _parse_board(board_text, game_number=state.variant.number)

    for melds in (state.melds_w, state.melds_b):
        meld_text = ",".join(_meld_text(meld) for meld in melds) or "-"
        _parse_melds(
            meld_text,
            game_number=state.variant.number,
            rules_mode=state.rules_mode,
        )
    for cooldowns in (state.cooldowns_w, state.cooldowns_b):
        _parse_cooldowns(_cooldown_text(cooldowns), rules_mode=state.rules_mode)


def serialize_clsn(state: GameState) -> str:
    """Serialize one Crownline game position into canonical CLSN1 text.

    CLSN is position notation, not replay notation. `ply` is deliberately
    excluded because it does not affect future legal play or scoring.
    """

    _validate_state(state)
    pieces = ",".join(
        f"{coord_to_alg(position)}:{_piece_text(piece)}"
        for position, piece in sorted(
            state.board.items(), key=lambda item: coord_to_alg(item[0])
        )
    ) or "-"
    melds_w = ",".join(
        _meld_text(meld)
        for meld in sorted(
            state.melds_w,
            key=lambda meld: (meld.line, meld.piece_ids, meld.points, meld.royal),
        )
    ) or "-"
    melds_b = ",".join(
        _meld_text(meld)
        for meld in sorted(
            state.melds_b,
            key=lambda meld: (meld.line, meld.piece_ids, meld.points, meld.royal),
        )
    ) or "-"
    end_reason = state.end_reason or "-"
    fields = (
        f"g={state.variant.number}",
        f"r={state.rules_mode}",
        f"t={state.turn}",
        f"b={state.capture_bank_w},{state.capture_bank_b}",
        f"q={state.triggering_player or '-'}",
        f"o={1 if state.game_over else 0}",
        f"e={end_reason}",
        f"p={pieces}",
        f"mw={melds_w}",
        f"mb={melds_b}",
        f"cw={_cooldown_text(state.cooldowns_w)}",
        f"cb={_cooldown_text(state.cooldowns_b)}",
    )
    return "|".join((CLSN_VERSION, *fields))


def parse_clsn(text: str) -> GameState:
    """Parse CLSN1 text into an authoritative GameState with ply reset to zero."""

    tokens = text.strip().split("|")
    if not tokens or tokens[0] != CLSN_VERSION:
        raise ValueError(f"CLSN must begin with {CLSN_VERSION}")

    fields: dict[str, str] = {}
    for token in tokens[1:]:
        if "=" not in token:
            raise ValueError(f"Invalid CLSN field {token!r}")
        key, value = token.split("=", 1)
        if key in fields:
            raise ValueError(f"Duplicate CLSN field {key!r}")
        fields[key] = value

    missing = [key for key in _FIELD_ORDER if key not in fields]
    unknown = [key for key in fields if key not in _FIELD_ORDER]
    if missing:
        raise ValueError(f"Missing CLSN fields: {', '.join(missing)}")
    if unknown:
        raise ValueError(f"Unknown CLSN fields: {', '.join(sorted(unknown))}")

    try:
        game_number = int(fields["g"])
    except ValueError as exc:
        raise ValueError("g must be 1 or 2") from exc
    variant = variant_for(game_number)
    rules_mode = normalize_rules_mode(fields["r"])

    turn = fields["t"]
    if turn not in ("W", "B"):
        raise ValueError("t must be W or B")

    bank_parts = fields["b"].split(",")
    if len(bank_parts) != 2:
        raise ValueError("b must contain White and Black capture banks")
    capture_bank_w = _parse_nonnegative_int(bank_parts[0], label="White capture bank")
    capture_bank_b = _parse_nonnegative_int(bank_parts[1], label="Black capture bank")

    trigger_text = fields["q"]
    if trigger_text not in ("-", "W", "B"):
        raise ValueError("q must be -, W, or B")
    triggering_player = None if trigger_text == "-" else trigger_text

    if fields["o"] not in ("0", "1"):
        raise ValueError("o must be 0 or 1")
    game_over = fields["o"] == "1"

    end_text = fields["e"]
    if end_text == "-":
        end_reason = None
    else:
        if _END_REASON_RE.fullmatch(end_text) is None:
            raise ValueError("e contains invalid characters")
        end_reason = end_text
    if game_over != (end_reason is not None):
        raise ValueError("o and e must agree about terminal status")

    board = _parse_board(fields["p"], game_number=game_number)
    melds_w = _parse_melds(
        fields["mw"], game_number=game_number, rules_mode=rules_mode
    )
    melds_b = _parse_melds(
        fields["mb"], game_number=game_number, rules_mode=rules_mode
    )
    cooldowns_w = _parse_cooldowns(fields["cw"], rules_mode=rules_mode)
    cooldowns_b = _parse_cooldowns(fields["cb"], rules_mode=rules_mode)

    state = GameState(
        board=board,
        variant=variant,
        rules_mode=rules_mode,
        turn=turn,
        capture_bank_w=capture_bank_w,
        capture_bank_b=capture_bank_b,
        melds_w=melds_w,
        melds_b=melds_b,
        cooldowns_w=cooldowns_w,
        cooldowns_b=cooldowns_b,
        triggering_player=triggering_player,  # type: ignore[arg-type]
        game_over=game_over,
        end_reason=end_reason,
        ply=0,
    )
    _validate_state(state)
    return state


def canonicalize_clsn(text: str) -> str:
    """Normalize valid CLSN1 input into its single canonical representation."""

    return serialize_clsn(parse_clsn(text))


def clsn_fingerprint(state: GameState) -> str:
    """Return SHA-256 of canonical CLSN1 text for exact-position comparison."""

    return hashlib.sha256(serialize_clsn(state).encode("ascii")).hexdigest()
