from __future__ import annotations

from dataclasses import dataclass, replace
from itertools import combinations
from typing import Dict, Iterable, Literal, Optional, Tuple

Player = Literal["W", "B"]
Coord = Tuple[int, int]  # (file 0..7, rank 1..8)

FILES = "abcdefgh"
CAPTURE_QUOTA = 15

CROWN_VALUES = {
    "b6": 8, "d6": 1, "f6": 6,
    "c5": 3, "e5": 5, "g5": 7,
    "b4": 4, "d4": 9, "f4": 2,
}

CROWN_LINES = (
    ("b6", "d6", "f6"),
    ("c5", "e5", "g5"),
    ("b4", "d4", "f4"),
    ("b6", "c5", "b4"),
    ("d6", "e5", "d4"),
    ("f6", "g5", "f4"),
    ("b6", "e5", "f4"),
    ("f6", "e5", "b4"),
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


def playable(coord: Coord) -> bool:
    f, r = coord
    return 0 <= f < 8 and 1 <= r <= 8 and ((f + 1) + r) % 2 == 0


def square_value(coord: Coord) -> int:
    alg = coord_to_alg(coord)
    if alg in CROWN_VALUES:
        return CROWN_VALUES[alg]
    rank = coord[1]
    return min(rank, 9 - rank, 4)


def opponent(player: Player) -> Player:
    return "B" if player == "W" else "W"


@dataclass(frozen=True)
class Piece:
    owner: Player
    value: int
    king: bool = False

    def capture_value(self) -> int:
        return self.value * (2 if self.king else 1)

    def token(self) -> str:
        return f"{self.owner}{self.value}{'K' if self.king else ''}"


@dataclass(frozen=True)
class Move:
    path: Tuple[Coord, ...]
    captured: Tuple[Coord, ...] = ()

    @property
    def is_capture(self) -> bool:
        return bool(self.captured)

    def notation(self) -> str:
        sep = "x" if self.is_capture else "-"
        return sep.join(coord_to_alg(c) for c in self.path)

    def __str__(self) -> str:
        return self.notation()


@dataclass(frozen=True)
class ScoreBreakdown:
    capture_bank: int
    board_value: int
    meld_count: int
    meld_bonus: int
    total: int
    melds: Tuple[Tuple[str, str, str], ...]


@dataclass(frozen=True)
class GameState:
    board: Dict[Coord, Piece]
    turn: Player = "W"
    capture_bank_w: int = 0
    capture_bank_b: int = 0
    triggering_player: Optional[Player] = None
    game_over: bool = False
    end_reason: Optional[str] = None
    ply: int = 0

    @classmethod
    def initial(cls) -> "GameState":
        board: Dict[Coord, Piece] = {}

        white_setup = {
            "a1": 1, "c1": 2, "e1": 3, "g1": 4,
            "b2": 5, "d2": 6,
        }
        black_setup = {
            "h8": 1, "f8": 2, "d8": 3, "b8": 4,
            "g7": 5, "e7": 6,
        }

        for sq, value in white_setup.items():
            board[alg_to_coord(sq)] = Piece("W", value)
        for sq, value in black_setup.items():
            board[alg_to_coord(sq)] = Piece("B", value)

        return cls(board=board)

    def bank(self, player: Player) -> int:
        return self.capture_bank_w if player == "W" else self.capture_bank_b

    def _with_bank(self, player: Player, amount: int) -> "GameState":
        if player == "W":
            return replace(self, capture_bank_w=amount)
        return replace(self, capture_bank_b=amount)

    def piece_at(self, square: str | Coord) -> Optional[Piece]:
        coord = alg_to_coord(square) if isinstance(square, str) else square
        return self.board.get(coord)

    def _dirs(self, piece: Piece) -> Tuple[Tuple[int, int], ...]:
        if piece.king:
            return ((-1, -1), (1, -1), (-1, 1), (1, 1))
        dr = 1 if piece.owner == "W" else -1
        return ((-1, dr), (1, dr))

    def _capture_sequences_from(
        self,
        board: Dict[Coord, Piece],
        start: Coord,
        piece: Piece,
    ) -> Tuple[Move, ...]:
        results = []

        def rec(
            cur_board: Dict[Coord, Piece],
            cur: Coord,
            cur_piece: Piece,
            path: Tuple[Coord, ...],
            captured: Tuple[Coord, ...],
        ) -> None:
            options = []
            cf, cr = cur

            for df, dr in self._dirs(cur_piece):
                mid = (cf + df, cr + dr)
                land = (cf + 2 * df, cr + 2 * dr)

                if not playable(land):
                    continue
                victim = cur_board.get(mid)
                if victim is None or victim.owner == cur_piece.owner:
                    continue
                if land in cur_board:
                    continue
                options.append((mid, land))

            if not options:
                if captured:
                    results.append(Move(path=path, captured=captured))
                return

            for mid, land in options:
                next_board = dict(cur_board)
                next_board.pop(cur)
                next_board.pop(mid)
                next_board[land] = cur_piece

                next_path = path + (land,)
                next_captured = captured + (mid,)

                # v0.1 rule: crowning ends the turn immediately.
                promotion_rank = 8 if cur_piece.owner == "W" else 1
                if not cur_piece.king and land[1] == promotion_rank:
                    results.append(Move(path=next_path, captured=next_captured))
                    continue

                rec(next_board, land, cur_piece, next_path, next_captured)

        rec(board, start, piece, (start,), ())
        return tuple(results)

    def legal_moves(self) -> Tuple[Move, ...]:
        if self.game_over:
            return ()

        captures = []
        for pos, piece in self.board.items():
            if piece.owner == self.turn:
                captures.extend(self._capture_sequences_from(self.board, pos, piece))

        if captures:
            return tuple(sorted(captures, key=lambda m: m.notation()))

        moves = []
        for pos, piece in self.board.items():
            if piece.owner != self.turn:
                continue
            f, r = pos
            for df, dr in self._dirs(piece):
                dst = (f + df, r + dr)
                if playable(dst) and dst not in self.board:
                    moves.append(Move(path=(pos, dst)))

        return tuple(sorted(moves, key=lambda m: m.notation()))

    def move_from_notation(self, notation: str) -> Move:
        normalized = notation.strip().lower().replace(" ", "")
        for move in self.legal_moves():
            if move.notation().lower() == normalized:
                return move
        legal = ", ".join(m.notation() for m in self.legal_moves())
        raise ValueError(f"Illegal move {notation!r}. Legal moves: {legal or '(none)'}")

    def apply_notation(self, notation: str) -> "GameState":
        return self.apply_move(self.move_from_notation(notation))

    def apply_move(self, move: Move) -> "GameState":
        if self.game_over:
            raise ValueError("Game is already over.")

        legal = self.legal_moves()
        if move not in legal:
            raise ValueError(
                f"Illegal move {move}. Legal moves: "
                + (", ".join(m.notation() for m in legal) or "(none)")
            )

        moving_piece = self.board[move.path[0]]
        board = dict(self.board)
        board.pop(move.path[0])

        capture_points = 0
        for captured_sq in move.captured:
            victim = board.pop(captured_sq)
            capture_points += victim.capture_value()

        destination = move.path[-1]
        promotion_rank = 8 if moving_piece.owner == "W" else 1
        if not moving_piece.king and destination[1] == promotion_rank:
            moving_piece = replace(moving_piece, king=True)

        board[destination] = moving_piece

        new_bank = self.bank(self.turn) + capture_points
        next_state = replace(
            self,
            board=board,
            ply=self.ply + 1,
        )._with_bank(self.turn, new_bank)

        # If a quota had already been triggered, this move was the opponent's
        # one final response turn.
        if self.triggering_player is not None:
            return replace(
                next_state,
                game_over=True,
                end_reason="final_response_completed",
            )

        # First quota crossing triggers exactly one opponent response turn.
        if new_bank >= CAPTURE_QUOTA:
            next_state = replace(next_state, triggering_player=self.turn)

        next_state = replace(next_state, turn=opponent(self.turn))

        # Turn-start immobilization check.
        if not next_state.legal_moves():
            next_state = replace(
                next_state,
                game_over=True,
                end_reason="immobilization",
            )

        return next_state

    def controlled_crownlines(self, player: Player) -> Tuple[Tuple[str, str, str], ...]:
        completed = []
        for line in CROWN_LINES:
            if all(
                (piece := self.board.get(alg_to_coord(sq))) is not None
                and piece.owner == player
                for sq in line
            ):
                completed.append(line)
        return tuple(completed)

    def scoring_melds(self, player: Player) -> Tuple[Tuple[str, str, str], ...]:
        lines = self.controlled_crownlines(player)
        best: Tuple[Tuple[str, str, str], ...] = ()

        # Brute force is tiny here: only eight possible Crownlines.
        for n in range(1, len(lines) + 1):
            for subset in combinations(lines, n):
                used = set()
                disjoint = True
                for line in subset:
                    if used.intersection(line):
                        disjoint = False
                        break
                    used.update(line)
                if disjoint and len(subset) > len(best):
                    best = subset

        return best

    def score(self, player: Player) -> ScoreBreakdown:
        board_value = sum(
            square_value(pos)
            for pos, piece in self.board.items()
            if piece.owner == player
        )
        melds = self.scoring_melds(player)
        meld_bonus = 15 * len(melds)
        capture_bank = self.bank(player)
        return ScoreBreakdown(
            capture_bank=capture_bank,
            board_value=board_value,
            meld_count=len(melds),
            meld_bonus=meld_bonus,
            total=capture_bank + board_value + meld_bonus,
            melds=melds,
        )

    def winner(self) -> Optional[Player | Literal["DRAW"]]:
        if not self.game_over:
            return None
        sw = self.score("W").total
        sb = self.score("B").total
        if sw > sb:
            return "W"
        if sb > sw:
            return "B"
        return "DRAW"

    def render(self) -> str:
        lines = []
        lines.append(
            f"Turn: {self.turn} | Bank W={self.capture_bank_w} B={self.capture_bank_b}"
            + (
                f" | Quota triggered by {self.triggering_player}"
                if self.triggering_player
                else ""
            )
        )
        if self.game_over:
            lines.append(f"GAME OVER: {self.end_reason} | Winner: {self.winner()}")

        for rank in range(8, 0, -1):
            row = [f"{rank} "]
            for f in range(8):
                pos = (f, rank)
                if not playable(pos):
                    cell = "    "
                else:
                    piece = self.board.get(pos)
                    if piece:
                        cell = f"{piece.token():>3} "
                    else:
                        alg = coord_to_alg(pos)
                        if alg in CROWN_VALUES:
                            cell = f"[{CROWN_VALUES[alg]}] "
                        else:
                            cell = " .  "
                row.append(cell)
            lines.append("".join(row))
        lines.append("   a   b   c   d   e   f   g   h")
        return "\n".join(lines)


def new_game() -> GameState:
    return GameState.initial()


if __name__ == "__main__":
    game = new_game()
    print(game.render())
    print("\nLegal opening moves:")
    print(", ".join(m.notation() for m in game.legal_moves()))
