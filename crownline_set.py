from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Literal, Optional, Tuple

from crownline_game import GameState, Line, Move
from crownline_rules import (
    OFFICIAL_RULES,
    Participant,
    Player,
    RulesMode,
    SetWinner,
    normalize_rules_mode,
    other_participant,
)


@dataclass(frozen=True)
class GameResult:
    game_number: Literal[1, 2]
    white_participant: Participant
    score_a: int
    score_b: int
    white_score: int
    black_score: int
    winner: Literal["A", "B", "DRAW"]
    end_reason: Optional[str]


@dataclass(frozen=True)
class CrownlineSet:
    first_game_white: Participant
    current_game: GameState
    rules_mode: RulesMode = OFFICIAL_RULES
    completed_games: Tuple[GameResult, ...] = ()
    carry_score_a: int = 0
    carry_score_b: int = 0
    set_index: int = 1
    set_over: bool = False

    @classmethod
    def initial(
        cls,
        first_game_white: Participant = "A",
        *,
        rules_mode: str = OFFICIAL_RULES,
        carry_score_a: int = 0,
        carry_score_b: int = 0,
        set_index: int = 1,
    ) -> "CrownlineSet":
        if first_game_white not in ("A", "B"):
            raise ValueError("first_game_white must be 'A' or 'B'")
        normalized_mode = normalize_rules_mode(rules_mode)
        return cls(
            first_game_white=first_game_white,
            current_game=GameState.initial(1, rules_mode=normalized_mode),
            rules_mode=normalized_mode,
            carry_score_a=carry_score_a,
            carry_score_b=carry_score_b,
            set_index=set_index,
        )

    @property
    def game_number(self) -> int:
        return self.current_game.variant.number

    @property
    def white_participant(self) -> Participant:
        return self.first_game_white if self.game_number == 1 else other_participant(self.first_game_white)

    @property
    def black_participant(self) -> Participant:
        return other_participant(self.white_participant)

    def participant_for_color(self, color: Player) -> Participant:
        return self.white_participant if color == "W" else self.black_participant

    def color_for_participant(self, participant: Participant) -> Player:
        return "W" if participant == self.white_participant else "B"

    def apply_move(self, move: Move, meld_line: Optional[Line] = None) -> "CrownlineSet":
        if self.set_over:
            raise ValueError("Set is already over")
        return replace(self, current_game=self.current_game.apply_move(move, meld_line=meld_line))

    def apply_notation(self, notation: str, meld_line: Optional[Line] = None) -> "CrownlineSet":
        return self.apply_move(self.current_game.move_from_notation(notation), meld_line=meld_line)

    def _result_for_current_game(self) -> GameResult:
        if not self.current_game.game_over:
            raise ValueError("Current game is not over")

        white_score = self.current_game.score("W").total
        black_score = self.current_game.score("B").total
        if self.white_participant == "A":
            score_a, score_b = white_score, black_score
        else:
            score_a, score_b = black_score, white_score

        winner = "A" if score_a > score_b else "B" if score_b > score_a else "DRAW"
        return GameResult(
            self.current_game.variant.number,
            self.white_participant,
            score_a,
            score_b,
            white_score,
            black_score,
            winner,
            self.current_game.end_reason,
        )

    def advance_game(self) -> "CrownlineSet":
        if self.set_over:
            raise ValueError("Set is already over")
        result = self._result_for_current_game()
        completed = self.completed_games + (result,)
        if self.game_number == 1:
            return replace(
                self,
                current_game=GameState.initial(2, rules_mode=self.rules_mode),
                completed_games=completed,
            )
        return replace(self, completed_games=completed, set_over=True)

    def aggregate_scores(self) -> Tuple[int, int]:
        return (
            self.carry_score_a + sum(result.score_a for result in self.completed_games),
            self.carry_score_b + sum(result.score_b for result in self.completed_games),
        )

    def winner(self) -> Optional[SetWinner]:
        if not self.set_over:
            return None
        score_a, score_b = self.aggregate_scores()
        return "A" if score_a > score_b else "B" if score_b > score_a else "DRAW"

    def continue_tied_set(self, next_first_game_white: Participant) -> "CrownlineSet":
        if not self.set_over:
            raise ValueError("Set must be complete before continuation")
        if self.winner() != "DRAW":
            raise ValueError("Only a tied set may continue under the official tie rule")
        score_a, score_b = self.aggregate_scores()
        return CrownlineSet.initial(
            first_game_white=next_first_game_white,
            rules_mode=self.rules_mode,
            carry_score_a=score_a,
            carry_score_b=score_b,
            set_index=self.set_index + 1,
        )


def new_set(
    first_game_white: Participant = "A",
    *,
    rules_mode: str = OFFICIAL_RULES,
) -> CrownlineSet:
    return CrownlineSet.initial(first_game_white=first_game_white, rules_mode=rules_mode)
