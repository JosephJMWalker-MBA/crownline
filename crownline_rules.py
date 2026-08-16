from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional, Tuple

Player = Literal["W", "B"]
Participant = Literal["A", "B"]
GameWinner = Literal["W", "B", "DRAW"]
SetWinner = Literal["A", "B", "DRAW"]
Coord = Tuple[int, int]
Line = Tuple[str, str, str]

FILES = "abcdefgh"
CAPTURE_QUOTA = 15
MELD_BONUS = 15

GAME1_CROWN_VALUES = (
    ("b6", 8), ("d6", 1), ("f6", 6),
    ("c5", 3), ("e5", 5), ("g5", 7),
    ("b4", 4), ("d4", 9), ("f4", 2),
)
GAME1_CROWN_LINES: Tuple[Line, ...] = (
    ("b6", "d6", "f6"),
    ("c5", "e5", "g5"),
    ("b4", "d4", "f4"),
    ("b6", "c5", "b4"),
    ("d6", "e5", "d4"),
    ("f6", "g5", "f4"),
    ("b6", "e5", "f4"),
    ("f6", "e5", "b4"),
)
GAME1_WHITE_SETUP = (
    ("a1", 1), ("c1", 2), ("e1", 3), ("g1", 4),
    ("b2", 5), ("d2", 6),
)
GAME1_BLACK_SETUP = (
    ("h8", 1), ("f8", 2), ("d8", 3), ("b8", 4),
    ("g7", 5), ("e7", 6),
)


def alg_to_coord(square: str) -> Coord:
    square = square.strip().lower()
    if len(square) != 2 or square[0] not in FILES or square[1] not in "12345678":
        raise ValueError(f"Invalid square: {square!r}")
    return FILES.index(square[0]), int(square[1])


def coord_to_alg(coord: Coord) -> str:
    f, r = coord
    if not (0 <= f < 8 and 1 <= r <= 8):
        raise ValueError(f"Invalid coordinate: {coord}")
    return f"{FILES[f]}{r}"


def mirror_file(square: str) -> str:
    f, r = alg_to_coord(square)
    return coord_to_alg((7 - f, r))


def _game2_values() -> Tuple[Tuple[str, int], ...]:
    return tuple((mirror_file(square), 10 - value) for square, value in GAME1_CROWN_VALUES)


def _game2_lines() -> Tuple[Line, ...]:
    return tuple(
        tuple(mirror_file(square) for square in line)  # type: ignore[misc]
        for line in GAME1_CROWN_LINES
    )


def _mirror_setup(setup: Tuple[Tuple[str, int], ...]) -> Tuple[Tuple[str, int], ...]:
    return tuple((mirror_file(square), value) for square, value in setup)


@dataclass(frozen=True)
class GameVariant:
    number: Literal[1, 2]
    name: str
    playable_parity: Literal[0, 1]
    crown_values: Tuple[Tuple[str, int], ...]
    crown_lines: Tuple[Line, ...]
    white_setup: Tuple[Tuple[str, int], ...]
    black_setup: Tuple[Tuple[str, int], ...]

    def playable(self, coord: Coord) -> bool:
        f, r = coord
        return (
            0 <= f < 8
            and 1 <= r <= 8
            and (((f + 1) + r) % 2 == self.playable_parity)
        )

    def square_value(self, coord: Coord) -> int:
        alg = coord_to_alg(coord)
        for square, value in self.crown_values:
            if square == alg:
                return value
        rank = coord[1]
        return min(rank, 9 - rank, 4)

    def crown_value(self, square: str) -> Optional[int]:
        square = square.lower()
        for candidate, value in self.crown_values:
            if candidate == square:
                return value
        return None


GAME1 = GameVariant(
    1,
    "Game 1 — dark / normal Lo Shu",
    0,
    GAME1_CROWN_VALUES,
    GAME1_CROWN_LINES,
    GAME1_WHITE_SETUP,
    GAME1_BLACK_SETUP,
)
GAME2 = GameVariant(
    2,
    "Game 2 — light / complementary Lo Shu",
    1,
    _game2_values(),
    _game2_lines(),
    _mirror_setup(GAME1_WHITE_SETUP),
    _mirror_setup(GAME1_BLACK_SETUP),
)

# Backward-compatible Game 1 aliases.
CROWN_VALUES = dict(GAME1.crown_values)
CROWN_LINES = GAME1.crown_lines


def variant_for(game_number: int) -> GameVariant:
    if game_number == 1:
        return GAME1
    if game_number == 2:
        return GAME2
    raise ValueError("game_number must be 1 or 2")


def playable(coord: Coord, game_number: int = 1) -> bool:
    return variant_for(game_number).playable(coord)


def square_value(coord: Coord, game_number: int = 1) -> int:
    return variant_for(game_number).square_value(coord)


def opponent(player: Player) -> Player:
    return "B" if player == "W" else "W"


def other_participant(participant: Participant) -> Participant:
    return "B" if participant == "A" else "A"
