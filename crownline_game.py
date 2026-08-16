from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Dict, Optional, Tuple

from crownline_rules import (
    CAPTURE_QUOTA,
    MELD_BONUS,
    MELD_COOLDOWN_TURNS,
    ROYAL_MELD_BONUS,
    Coord,
    GAME1,
    GameVariant,
    GameWinner,
    Line,
    OFFICIAL_RULES,
    Player,
    RulesMode,
    alg_to_coord,
    coord_to_alg,
    normalize_rules_mode,
    opponent,
    uses_crowned_meld,
    uses_sovereign_king,
    variant_for,
)


@dataclass(frozen=True)
class Piece:
    owner: Player
    value: int
    king: bool = False

    def __post_init__(self) -> None:
        if self.value not in range(1, 7):
            raise ValueError("Piece value/identity must be between 1 and 6")

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
class Meld:
    line: Line
    piece_ids: Tuple[int, int, int]
    points: int = MELD_BONUS
    royal: bool = False


class MeldChoiceRequired(ValueError):
    def __init__(self, options: Tuple[Meld, ...]):
        self.options = options
        rendered = ", ".join("-".join(meld.line) for meld in options)
        super().__init__(f"Move completes multiple eligible Crownlines; choose one: {rendered}")


@dataclass(frozen=True)
class ScoreBreakdown:
    capture_bank: int
    board_value: int
    meld_count: int
    meld_bonus: int
    total: int
    melds: Tuple[Meld, ...]


Cooldowns = Tuple[Tuple[int, int], ...]


@dataclass(frozen=True)
class GameState:
    board: Dict[Coord, Piece]
    variant: GameVariant = GAME1
    rules_mode: RulesMode = OFFICIAL_RULES
    turn: Player = "W"
    capture_bank_w: int = 0
    capture_bank_b: int = 0
    melds_w: Tuple[Meld, ...] = ()
    melds_b: Tuple[Meld, ...] = ()
    cooldowns_w: Cooldowns = ()
    cooldowns_b: Cooldowns = ()
    triggering_player: Optional[Player] = None
    game_over: bool = False
    end_reason: Optional[str] = None
    ply: int = 0

    def __post_init__(self) -> None:
        normalize_rules_mode(self.rules_mode)

    @classmethod
    def initial(cls, game_number: int = 1, rules_mode: str = OFFICIAL_RULES) -> "GameState":
        variant = variant_for(game_number)
        normalized_mode = normalize_rules_mode(rules_mode)
        board: Dict[Coord, Piece] = {}
        for square, value in variant.white_setup:
            board[alg_to_coord(square)] = Piece("W", value)
        for square, value in variant.black_setup:
            board[alg_to_coord(square)] = Piece("B", value)
        return cls(board=board, variant=variant, rules_mode=normalized_mode)

    def bank(self, player: Player) -> int:
        return self.capture_bank_w if player == "W" else self.capture_bank_b

    def melds(self, player: Player) -> Tuple[Meld, ...]:
        return self.melds_w if player == "W" else self.melds_b

    def used_piece_ids(self, player: Player) -> frozenset[int]:
        return frozenset(piece_id for meld in self.melds(player) for piece_id in meld.piece_ids)

    def retired_lines(self, player: Player) -> frozenset[Line]:
        """Crowned-style lines already scored by this player in this game."""
        if not uses_crowned_meld(self.rules_mode):
            return frozenset()
        return frozenset(meld.line for meld in self.melds(player))

    def cooldowns(self, player: Player) -> Dict[int, int]:
        source = self.cooldowns_w if player == "W" else self.cooldowns_b
        return dict(source)

    def piece_cooldown(self, player: Player, piece_id: int) -> int:
        return self.cooldowns(player).get(piece_id, 0)

    def _with_bank(self, player: Player, amount: int) -> "GameState":
        return replace(self, **({"capture_bank_w": amount} if player == "W" else {"capture_bank_b": amount}))

    def _with_meld(self, player: Player, meld: Meld) -> "GameState":
        if player == "W":
            return replace(self, melds_w=self.melds_w + (meld,))
        return replace(self, melds_b=self.melds_b + (meld,))

    def _with_cooldowns(self, player: Player, cooldowns: Dict[int, int]) -> "GameState":
        packed = tuple(sorted((piece_id, turns) for piece_id, turns in cooldowns.items() if turns > 0))
        if player == "W":
            return replace(self, cooldowns_w=packed)
        return replace(self, cooldowns_b=packed)

    def _advance_cooldowns_after_turn(self, player: Player, new_meld: Optional[Meld]) -> "GameState":
        if not uses_crowned_meld(self.rules_mode):
            return self
        cooldowns = {
            piece_id: turns - 1
            for piece_id, turns in self.cooldowns(player).items()
            if turns > 1
        }
        if new_meld is not None:
            for piece_id in new_meld.piece_ids:
                cooldowns[piece_id] = MELD_COOLDOWN_TURNS
        return self._with_cooldowns(player, cooldowns)

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

        def rec(current_board, current, current_piece, path, captured):
            options = []
            cf, cr = current
            for df, dr in self._dirs(current_piece):
                middle = (cf + df, cr + dr)
                landing = (cf + 2 * df, cr + 2 * dr)
                if not self.variant.playable(landing):
                    continue
                victim = current_board.get(middle)
                if victim is None or victim.owner == current_piece.owner or landing in current_board:
                    continue
                options.append((middle, landing))

            if not options:
                if captured:
                    results.append(Move(path=path, captured=captured))
                return

            for middle, landing in options:
                next_board = dict(current_board)
                next_board.pop(current)
                next_board.pop(middle)
                next_board[landing] = current_piece
                next_path = path + (landing,)
                next_captured = captured + (middle,)
                promotion_rank = 8 if current_piece.owner == "W" else 1
                if not current_piece.king and landing[1] == promotion_rank:
                    results.append(Move(path=next_path, captured=next_captured))
                    continue
                rec(next_board, landing, current_piece, next_path, next_captured)

        rec(board, start, piece, (start,), ())
        return tuple(results)

    def _simple_moves(self, *, kings_only: bool = False) -> Tuple[Move, ...]:
        moves = []
        for position, piece in self.board.items():
            if piece.owner != self.turn or (kings_only and not piece.king):
                continue
            f, r = position
            for df, dr in self._dirs(piece):
                destination = (f + df, r + dr)
                if self.variant.playable(destination) and destination not in self.board:
                    moves.append(Move(path=(position, destination)))
        return tuple(sorted(moves, key=lambda move: move.notation()))

    def legal_moves(self) -> Tuple[Move, ...]:
        if self.game_over:
            return ()

        captures = []
        sovereign_king_can_capture = False
        for position, piece in self.board.items():
            if piece.owner != self.turn:
                continue
            piece_captures = self._capture_sequences_from(self.board, position, piece)
            captures.extend(piece_captures)
            if piece.king and piece_captures:
                sovereign_king_can_capture = True

        if captures:
            # Sovereignty releases the capture obligation for the whole turn only
            # when a King could have satisfied that obligation. The player may
            # then choose any otherwise legal non-capturing move, including with
            # a different ordinary piece. If only ordinary pieces can capture,
            # mandatory capture still binds the turn.
            if uses_sovereign_king(self.rules_mode) and sovereign_king_can_capture:
                captures.extend(self._simple_moves())
            return tuple(sorted(captures, key=lambda move: move.notation()))

        return self._simple_moves()

    def move_from_notation(self, notation: str) -> Move:
        normalized = notation.strip().lower().replace(" ", "")
        for move in self.legal_moves():
            if move.notation().lower() == normalized:
                return move
        legal = ", ".join(move.notation() for move in self.legal_moves())
        raise ValueError(f"Illegal move {notation!r}. Legal moves: {legal or '(none)'}")

    def _executed_position(self, move: Move):
        moving_piece = self.board[move.path[0]]
        board = dict(self.board)
        board.pop(move.path[0])
        capture_points = 0
        for captured_square in move.captured:
            capture_points += board.pop(captured_square).capture_value()
        destination = move.path[-1]
        promotion_rank = 8 if moving_piece.owner == "W" else 1
        if not moving_piece.king and destination[1] == promotion_rank:
            moving_piece = replace(moving_piece, king=True)
        board[destination] = moving_piece
        return board, capture_points

    def _line_owned(self, board: Dict[Coord, Piece], line: Line, player: Player) -> bool:
        return all(
            (piece := board.get(alg_to_coord(square))) is not None and piece.owner == player
            for square in line
        )

    def crowned_meld_diagnostics_on_board(
        self,
        board: Dict[Coord, Piece],
        player: Player,
        *,
        previous_board: Optional[Dict[Coord, Piece]] = None,
    ) -> Tuple[dict, ...]:
        """Explain visible newly completed Crownlines that cannot score.

        This is authoritative rules feedback for the client; the browser should
        render these reasons rather than reimplementing Crowned Meld eligibility.
        """
        if not uses_crowned_meld(self.rules_mode):
            return ()

        cooldowns = self.cooldowns(player)
        retired = self.retired_lines(player)
        diagnostics = []
        for line in self.variant.crown_lines:
            if not self._line_owned(board, line, player):
                continue
            if previous_board is not None and self._line_owned(previous_board, line, player):
                continue

            pieces = tuple(board[alg_to_coord(square)] for square in line)
            piece_ids = tuple(piece.value for piece in pieces)
            reasons = []
            if line in retired:
                reasons.append({
                    "code": "retired_line",
                    "message": "You already scored this Crownline; it is retired for you this game.",
                })
            if len(set(piece_ids)) != 3:
                reasons.append({
                    "code": "duplicate_identity",
                    "message": "A Crownline needs three distinct piece identities.",
                })
            blocked = [
                {"piece_id": piece_id, "turns": cooldowns[piece_id]}
                for piece_id in piece_ids
                if cooldowns.get(piece_id, 0) > 0
            ]
            if blocked:
                detail = ", ".join(
                    f"piece {item['piece_id']} ({item['turns']} turn{'s' if item['turns'] != 1 else ''})"
                    for item in blocked
                )
                reasons.append({
                    "code": "cooldown",
                    "message": f"Crownline cooldown remains on {detail}.",
                    "pieces": blocked,
                })
            if not any(piece.king for piece in pieces):
                reasons.append({
                    "code": "king_required",
                    "message": "Crowned Meld requires at least one King in the formation.",
                })
            if reasons:
                diagnostics.append({
                    "line": line,
                    "piece_ids": piece_ids,
                    "reasons": tuple(reasons),
                })
        return tuple(diagnostics)

    def crowned_meld_diagnostics_after(self, move: Move) -> Tuple[dict, ...]:
        if move not in self.legal_moves():
            raise ValueError(f"Illegal move {move}")
        board, _ = self._executed_position(move)
        return self.crowned_meld_diagnostics_on_board(board, self.turn, previous_board=self.board)

    def eligible_melds_on_board(
        self,
        board: Dict[Coord, Piece],
        player: Player,
        *,
        previous_board: Optional[Dict[Coord, Piece]] = None,
    ) -> Tuple[Meld, ...]:
        options = []

        if uses_crowned_meld(self.rules_mode):
            cooldowns = self.cooldowns(player)
            retired = self.retired_lines(player)
            for line in self.variant.crown_lines:
                if not self._line_owned(board, line, player):
                    continue
                # A standing formation never scores merely because cooldown expires.
                if previous_board is not None and self._line_owned(previous_board, line, player):
                    continue
                # Retirement is per player: the opponent may still score this geometry.
                if line in retired:
                    continue
                pieces = tuple(board[alg_to_coord(square)] for square in line)
                piece_ids = tuple(piece.value for piece in pieces)
                if len(set(piece_ids)) != 3:
                    continue
                if any(cooldowns.get(piece_id, 0) > 0 for piece_id in piece_ids):
                    continue
                king_count = sum(piece.king for piece in pieces)
                if king_count == 0:
                    continue
                royal = king_count == 3
                options.append(
                    Meld(
                        line=line,
                        piece_ids=piece_ids,
                        points=ROYAL_MELD_BONUS if royal else MELD_BONUS,
                        royal=royal,
                    )
                )
            return tuple(options)

        used = self.used_piece_ids(player)
        for line in self.variant.crown_lines:
            pieces = [board.get(alg_to_coord(square)) for square in line]
            if not all(piece is not None and piece.owner == player for piece in pieces):
                continue
            piece_ids = tuple(piece.value for piece in pieces if piece is not None)
            if len(piece_ids) == 3 and len(set(piece_ids)) == 3 and set(piece_ids).isdisjoint(used):
                options.append(Meld(line=line, piece_ids=piece_ids))
        return tuple(options)

    def meld_options_after(self, move: Move) -> Tuple[Meld, ...]:
        if move not in self.legal_moves():
            raise ValueError(f"Illegal move {move}")
        board, _ = self._executed_position(move)
        return self.eligible_melds_on_board(board, self.turn, previous_board=self.board)

    def apply_notation(self, notation: str, meld_line: Optional[Line] = None) -> "GameState":
        return self.apply_move(self.move_from_notation(notation), meld_line=meld_line)

    def apply_move(self, move: Move, meld_line: Optional[Line] = None) -> "GameState":
        if self.game_over:
            raise ValueError("Game is already over.")
        legal = self.legal_moves()
        if move not in legal:
            legal_text = ", ".join(candidate.notation() for candidate in legal) or "(none)"
            raise ValueError(f"Illegal move {move}. Legal moves: {legal_text}")

        board, capture_points = self._executed_position(move)
        options = self.eligible_melds_on_board(board, self.turn, previous_board=self.board)
        chosen_meld: Optional[Meld] = None

        if len(options) == 1:
            if meld_line is not None and meld_line != options[0].line:
                raise ValueError("Requested meld_line is not the eligible Crownline")
            chosen_meld = options[0]
        elif len(options) > 1:
            if meld_line is None:
                raise MeldChoiceRequired(options)
            chosen_meld = next((meld for meld in options if meld.line == meld_line), None)
            if chosen_meld is None:
                raise ValueError("Requested meld_line is not one of the eligible Crownlines")
        elif meld_line is not None:
            raise ValueError("No eligible Crownline is available after this move")

        new_bank = self.bank(self.turn) + capture_points
        next_state = replace(self, board=board, ply=self.ply + 1)._with_bank(self.turn, new_bank)
        if chosen_meld is not None:
            next_state = next_state._with_meld(self.turn, chosen_meld)
        next_state = next_state._advance_cooldowns_after_turn(self.turn, chosen_meld)

        if self.triggering_player is not None:
            return replace(next_state, game_over=True, end_reason="final_response_completed")

        if new_bank >= CAPTURE_QUOTA:
            next_state = replace(next_state, triggering_player=self.turn)

        next_state = replace(next_state, turn=opponent(self.turn))
        if not next_state.legal_moves():
            next_state = replace(next_state, game_over=True, end_reason="immobilization")
        return next_state

    def controlled_crownlines(self, player: Player) -> Tuple[Line, ...]:
        return tuple(
            line
            for line in self.variant.crown_lines
            if self._line_owned(self.board, line, player)
        )

    def score(self, player: Player) -> ScoreBreakdown:
        board_value = sum(
            self.variant.square_value(position)
            for position, piece in self.board.items()
            if piece.owner == player
        )
        melds = self.melds(player)
        meld_bonus = sum(meld.points for meld in melds)
        capture_bank = self.bank(player)
        return ScoreBreakdown(
            capture_bank,
            board_value,
            len(melds),
            meld_bonus,
            capture_bank + board_value + meld_bonus,
            melds,
        )

    def winner(self) -> Optional[GameWinner]:
        if not self.game_over:
            return None
        white, black = self.score("W").total, self.score("B").total
        return "W" if white > black else "B" if black > white else "DRAW"

    def render(self) -> str:
        header = (
            f"{self.variant.name} | Rules: {self.rules_mode} | Turn: {self.turn} | "
            f"Bank W={self.capture_bank_w} B={self.capture_bank_b} | "
            f"Melds W={len(self.melds_w)} B={len(self.melds_b)}"
        )
        if self.triggering_player:
            header += f" | Quota triggered by {self.triggering_player}"
        lines = [header]
        if self.game_over:
            lines.append(f"GAME OVER: {self.end_reason} | Winner: {self.winner()}")

        crown_values = dict(self.variant.crown_values)
        for rank in range(8, 0, -1):
            row = [f"{rank} "]
            for file_index in range(8):
                position = (file_index, rank)
                if not self.variant.playable(position):
                    cell = "    "
                elif (piece := self.board.get(position)) is not None:
                    cooldown = self.piece_cooldown(piece.owner, piece.value)
                    suffix = f"^{cooldown}" if cooldown else ""
                    cell = f"{piece.token() + suffix:>3} "
                else:
                    alg = coord_to_alg(position)
                    cell = f"[{crown_values[alg]}] " if alg in crown_values else " .  "
                row.append(cell)
            lines.append("".join(row))
        lines.append("   a   b   c   d   e   f   g   h")
        return "\n".join(lines)


def new_game(game_number: int = 1, rules_mode: str = OFFICIAL_RULES) -> GameState:
    return GameState.initial(game_number, rules_mode=rules_mode)
