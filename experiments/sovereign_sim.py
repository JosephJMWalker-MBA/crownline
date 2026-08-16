"""Compare Official Crownline v1.0 with the experimental Sovereign King rule.

The experiment never changes RULES.md or the production engine on disk. It
monkeypatches GameState.legal_moves for the duration of a simulation process and
restores the original method before exit.
"""
from __future__ import annotations

import argparse
import random
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from crownline_game import GameState, Move
from crownline_rules import alg_to_coord
from crownline_set import new_set

ORIGINAL_LEGAL_MOVES = GameState.legal_moves


def capture_moves(game: GameState):
    moves = []
    for position, piece in game.board.items():
        if piece.owner == game.turn:
            moves.extend(game._capture_sequences_from(game.board, position, piece))
    return tuple(sorted(moves, key=lambda move: move.notation()))


def simple_moves(game: GameState, *, kings_only: bool = False):
    moves = []
    for position, piece in game.board.items():
        if piece.owner != game.turn or (kings_only and not piece.king):
            continue
        f, r = position
        for df, dr in game._dirs(piece):
            destination = (f + df, r + dr)
            if game.variant.playable(destination) and destination not in game.board:
                moves.append(Move(path=(position, destination)))
    return tuple(sorted(moves, key=lambda move: move.notation()))


def sovereign_legal_moves(self: GameState):
    """Full-strength candidate: Kings may step normally despite any capture."""
    if self.game_over:
        return ()
    captures = capture_moves(self)
    if captures:
        return tuple(sorted(captures + simple_moves(self, kings_only=True), key=lambda move: move.notation()))
    return simple_moves(self)


def crown_potential(game: GameState, board, color: str) -> float:
    used = game.used_piece_ids(color)
    value = 0.0
    for line in game.variant.crown_lines:
        own = 0
        eligible = 0
        blocked = False
        for square in line:
            piece = board.get(alg_to_coord(square))
            if piece is None:
                continue
            if piece.owner != color:
                blocked = True
                break
            own += 1
            if piece.value not in used:
                eligible += 1
        if blocked:
            continue
        if own == 2 and eligible == 2:
            value += 5.0
        elif own == 1 and eligible == 1:
            value += 1.0
    return value


def choose_action(state, rng: random.Random, policy: str):
    game = state.current_game
    moves = game.legal_moves()
    if policy == "random":
        move = rng.choice(moves)
    else:
        best_score = float("-inf")
        best_moves = []
        for candidate in moves:
            board, capture_points = game._executed_position(candidate)
            mover = game.turn
            moving_piece = game.board[candidate.path[0]]
            after_piece = board.get(candidate.path[-1])
            promoted = bool(after_piece and not moving_piece.king and after_piece.king)
            melds = game.eligible_melds_on_board(board, mover)
            score = capture_points * 8
            score += game.variant.square_value(candidate.path[-1]) * 2
            score += crown_potential(game, board, mover) * 3
            score += len(melds) * 45
            score += 10 if promoted else 0
            score += rng.random() * 0.001
            if score > best_score:
                best_score = score
                best_moves = [candidate]
            elif abs(score - best_score) < 1e-9:
                best_moves.append(candidate)
        move = rng.choice(best_moves)

    melds = game.meld_options_after(move)
    meld_line = rng.choice(melds).line if melds else None
    return move, meld_line


@dataclass
class GameTrack:
    captures: int = 0
    capture_points: int = 0
    promotions: int = 0
    king_captures: int = 0
    sovereign_opportunities: int = 0
    sovereign_refusals: int = 0


def play_set(rule: str, policy: str, seed: int, max_game_plies: int):
    GameState.legal_moves = ORIGINAL_LEGAL_MOVES if rule == "v1" else sovereign_legal_moves
    rng = random.Random(seed)
    state = new_set(first_game_white="A" if seed % 2 == 0 else "B")
    games = []
    track = GameTrack()

    while not state.set_over:
        game = state.current_game
        if game.game_over:
            games.append({
                "plies": game.ply,
                "captures": track.captures,
                "capture_points": track.capture_points,
                "promotions": track.promotions,
                "king_captures": track.king_captures,
                "melds": len(game.melds_w) + len(game.melds_b),
                "sovereign_opportunities": track.sovereign_opportunities,
                "sovereign_refusals": track.sovereign_refusals,
                "end_reason": game.end_reason,
            })
            state = state.advance_game()
            track = GameTrack()
            continue

        if game.ply >= max_game_plies:
            games.append({
                "plies": game.ply,
                "captures": track.captures,
                "capture_points": track.capture_points,
                "promotions": track.promotions,
                "king_captures": track.king_captures,
                "melds": len(game.melds_w) + len(game.melds_b),
                "sovereign_opportunities": track.sovereign_opportunities,
                "sovereign_refusals": track.sovereign_refusals,
                "end_reason": "ply_cap",
            })
            return {"winner": None, "margin": None, "games": games, "capped": True}

        available_captures = capture_moves(game)
        if rule == "sovereign" and available_captures and simple_moves(game, kings_only=True):
            track.sovereign_opportunities += 1

        move, meld_line = choose_action(state, rng, policy)
        moving_piece = game.board[move.path[0]]
        if rule == "sovereign" and available_captures and not move.is_capture and moving_piece.king:
            track.sovereign_refusals += 1

        track.captures += len(move.captured)
        track.capture_points += sum(game.board[square].capture_value() for square in move.captured)
        track.king_captures += sum(int(game.board[square].king) for square in move.captured)

        child = state.apply_move(move, meld_line=meld_line)
        after_piece = child.current_game.board.get(move.path[-1])
        track.promotions += int(bool(after_piece and not moving_piece.king and after_piece.king))
        state = child

    score_a, score_b = state.aggregate_scores()
    return {
        "winner": state.winner(),
        "margin": score_a - score_b,
        "games": games,
        "capped": False,
    }


def summarize(records):
    completed = [record for record in records if not record["capped"]]
    games = [game for record in records for game in record["games"]]
    winners = Counter(record["winner"] for record in completed)
    endings = Counter(game["end_reason"] for game in games)
    opportunities = sum(game["sovereign_opportunities"] for game in games)
    refusals = sum(game["sovereign_refusals"] for game in games)

    def average(key):
        return sum(game[key] for game in games) / len(games)

    return {
        "sets": len(records),
        "completed_sets": len(completed),
        "capped_sets_pct": 100 * (len(records) - len(completed)) / len(records),
        "A_win_pct": 100 * winners["A"] / len(completed) if completed else 0,
        "B_win_pct": 100 * winners["B"] / len(completed) if completed else 0,
        "draw_pct": 100 * winners["DRAW"] / len(completed) if completed else 0,
        "mean_margin_A_minus_B": sum(record["margin"] for record in completed) / len(completed) if completed else 0,
        "mean_abs_margin": sum(abs(record["margin"]) for record in completed) / len(completed) if completed else 0,
        "avg_plies_per_game": average("plies"),
        "avg_captures_per_game": average("captures"),
        "avg_capture_points_per_game": average("capture_points"),
        "avg_promotions_per_game": average("promotions"),
        "promotion_game_pct": 100 * sum(game["promotions"] > 0 for game in games) / len(games),
        "avg_king_captures_per_game": average("king_captures"),
        "avg_melds_per_game": average("melds"),
        "meld_game_pct": 100 * sum(game["melds"] > 0 for game in games) / len(games),
        "quota_end_pct": 100 * endings["final_response_completed"] / len(games),
        "immobilization_pct": 100 * endings["immobilization"] / len(games),
        "ply_cap_game_pct": 100 * endings["ply_cap"] / len(games),
        "sovereign_opportunities_per_game": opportunities / len(games),
        "sovereign_refusal_rate_pct": 100 * refusals / opportunities if opportunities else 0,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sets", type=int, default=100)
    parser.add_argument("--policy", choices=("random", "heuristic"), default="random")
    parser.add_argument("--max-game-plies", type=int, default=250)
    parser.add_argument("--seed", type=int, default=51000000)
    args = parser.parse_args()

    try:
        for rule in ("v1", "sovereign"):
            records = [
                play_set(rule, args.policy, args.seed + index, args.max_game_plies)
                for index in range(args.sets)
            ]
            print(rule, summarize(records))
    finally:
        GameState.legal_moves = ORIGINAL_LEGAL_MOVES


if __name__ == "__main__":
    main()
