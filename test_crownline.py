from dataclasses import replace
import pytest

import crownline as c


def C(s):
    return c.alg_to_coord(s)


def test_game1_opening_moves_preserved():
    g = c.new_game(1)
    moves = {m.notation() for m in g.legal_moves()}
    assert "d2-e3" in moves
    assert "b2-c3" in moves
    assert all("x" not in m for m in moves)


def test_mandatory_capture():
    g = c.GameState(
        board={
            C("c3"): c.Piece("W", 2),
            C("d4"): c.Piece("B", 4),
            C("g1"): c.Piece("W", 1),
        },
        turn="W",
    )
    assert [m.notation() for m in g.legal_moves()] == ["c3xe5"]


def test_multi_jump():
    g = c.GameState(
        board={
            C("a3"): c.Piece("W", 3),
            C("b4"): c.Piece("B", 1),
            C("d6"): c.Piece("B", 2),
        },
        turn="W",
    )
    assert [m.notation() for m in g.legal_moves()] == ["a3xc5xe7"]


def test_crowning_ends_capture_chain():
    g = c.GameState(
        board={
            C("f6"): c.Piece("W", 5),
            C("g7"): c.Piece("B", 2),
            C("f8"): c.Piece("B", 3),
        },
        turn="W",
    )
    assert [m.notation() for m in g.legal_moves()] == ["f6xh8"]
    assert g.apply_notation("f6xh8").piece_at("h8").king


def test_king_capture_value_doubles():
    g = c.GameState(
        board={
            C("c3"): c.Piece("W", 1),
            C("d4"): c.Piece("B", 6, king=True),
            C("a7"): c.Piece("B", 1),
        },
        turn="W",
    )
    g2 = g.apply_notation("c3xe5")
    assert g2.capture_bank_w == 12


def test_game2_uses_light_squares_and_mirrored_setup():
    g = c.new_game(2)
    assert g.variant.number == 2
    assert g.piece_at("h1") == c.Piece("W", 1)
    assert g.piece_at("f1") == c.Piece("W", 2)
    assert g.piece_at("a8") == c.Piece("B", 1)
    assert g.piece_at("b7") == c.Piece("B", 5)
    assert g.variant.playable(C("h1"))
    assert not g.variant.playable(C("a1"))


def test_game2_crown_grid_is_complementary_and_every_line_sums_to_15():
    expected = {
        "g6": 2, "e6": 9, "c6": 4,
        "f5": 7, "d5": 5, "b5": 3,
        "g4": 6, "e4": 1, "c4": 8,
    }
    assert dict(c.GAME2.crown_values) == expected
    for line in c.GAME2.crown_lines:
        assert sum(c.GAME2.crown_value(sq) for sq in line) == 15


def test_single_meld_banks_immediately():
    g = c.GameState(
        board={
            C("b4"): c.Piece("W", 1),
            C("d4"): c.Piece("W", 2),
            C("e3"): c.Piece("W", 3),
            C("a7"): c.Piece("B", 4),
        },
        variant=c.GAME1,
        turn="W",
    )
    g2 = g.apply_notation("e3-f4")
    assert len(g2.melds_w) == 1
    assert g2.melds_w[0].line == ("b4", "d4", "f4")
    assert set(g2.melds_w[0].piece_ids) == {1, 2, 3}
    assert g2.score("W").meld_bonus == 15


def test_banked_meld_persists_after_line_disappears():
    meld = c.Meld(("b4", "d4", "f4"), (1, 2, 3))
    g = c.GameState(
        board={
            C("b4"): c.Piece("W", 1),
            C("d4"): c.Piece("W", 2),
            C("g5"): c.Piece("W", 3),
            C("a7"): c.Piece("B", 4),
        },
        variant=c.GAME1,
        melds_w=(meld,),
    )
    assert g.controlled_crownlines("W") == ()
    assert g.score("W").meld_count == 1
    assert g.score("W").meld_bonus == 15


def test_meld_used_piece_cannot_score_again():
    old = c.Meld(("b4", "d4", "f4"), (1, 2, 3))
    g = c.GameState(
        board={
            C("c5"): c.Piece("W", 1),
            C("g5"): c.Piece("W", 4),
            C("d4"): c.Piece("W", 5),
            C("a7"): c.Piece("B", 6),
        },
        variant=c.GAME1,
        turn="W",
        melds_w=(old,),
    )
    move = g.move_from_notation("d4-e5")
    assert g.meld_options_after(move) == ()


def test_multiple_new_lines_require_player_meld_choice():
    g = c.GameState(
        board={
            C("c5"): c.Piece("W", 1),
            C("g5"): c.Piece("W", 2),
            C("b6"): c.Piece("W", 3),
            C("f4"): c.Piece("W", 4),
            C("d4"): c.Piece("W", 5),
            C("a7"): c.Piece("B", 6),
        },
        variant=c.GAME1,
        turn="W",
    )
    move = g.move_from_notation("d4-e5")
    options = g.meld_options_after(move)
    assert {m.line for m in options} == {
        ("c5", "e5", "g5"),
        ("b6", "e5", "f4"),
    }
    with pytest.raises(c.MeldChoiceRequired):
        g.apply_move(move)

    chosen = ("b6", "e5", "f4")
    g2 = g.apply_move(move, meld_line=chosen)
    assert len(g2.melds_w) == 1
    assert g2.melds_w[0].line == chosen
    assert set(g2.used_piece_ids("W")) == {3, 4, 5}


def test_quota_gives_exactly_one_response_turn():
    g = c.GameState(
        board={
            C("c3"): c.Piece("W", 1),
            C("d4"): c.Piece("B", 6),
            C("g7"): c.Piece("B", 5),
            C("a1"): c.Piece("W", 2),
        },
        variant=c.GAME1,
        turn="W",
        capture_bank_w=9,
    )
    g = g.apply_notation("c3xe5")
    assert g.triggering_player == "W"
    assert g.turn == "B"
    assert not g.game_over

    g = g.apply_move(g.legal_moves()[0])
    assert g.game_over
    assert g.end_reason == "final_response_completed"


def test_set_swaps_colors_and_game_variant():
    s = c.new_set(first_game_white="A")
    assert s.game_number == 1
    assert s.white_participant == "A"
    assert s.black_participant == "B"

    ended = replace(s.current_game, game_over=True, end_reason="test_terminal")
    s = replace(s, current_game=ended).advance_game()
    assert s.game_number == 2
    assert s.white_participant == "B"
    assert s.black_participant == "A"
    assert s.current_game.variant is c.GAME2


def test_set_aggregate_maps_color_scores_back_to_participants():
    s = c.new_set(first_game_white="A")
    g1 = replace(s.current_game, game_over=True, end_reason="test_terminal")
    g1_w = g1.score("W").total
    g1_b = g1.score("B").total
    s = replace(s, current_game=g1).advance_game()

    g2 = replace(s.current_game, game_over=True, end_reason="test_terminal")
    g2_w = g2.score("W").total
    g2_b = g2.score("B").total
    s = replace(s, current_game=g2).advance_game()

    assert s.set_over
    assert s.aggregate_scores() == (g1_w + g2_b, g1_b + g2_w)


def test_tied_set_can_continue_with_aggregate_carried_forward():
    s = c.new_set(first_game_white="A")
    r1 = c.GameResult(1, "A", 20, 20, 20, 20, "DRAW", "test")
    r2 = c.GameResult(2, "B", 30, 30, 30, 30, "DRAW", "test")
    s = replace(s, completed_games=(r1, r2), set_over=True)
    assert s.winner() == "DRAW"
    assert s.aggregate_scores() == (50, 50)

    continued = s.continue_tied_set(next_first_game_white="B")
    assert continued.set_index == 2
    assert continued.first_game_white == "B"
    assert continued.aggregate_scores() == (50, 50)
    assert continued.game_number == 1
    assert not continued.set_over


def test_non_tied_set_cannot_continue():
    s = c.new_set()
    r1 = c.GameResult(1, "A", 21, 20, 21, 20, "A", "test")
    r2 = c.GameResult(2, "B", 30, 30, 30, 30, "DRAW", "test")
    s = replace(s, completed_games=(r1, r2), set_over=True)
    assert s.winner() == "A"
    with pytest.raises(ValueError):
        s.continue_tied_set("A")
