from dataclasses import replace

import crownline as c


def C(square):
    return c.alg_to_coord(square)


def forming_position(*, kings=(False, False, False), cooldowns=(), melds=()):
    before = {
        C("b4"): c.Piece("W", 1, king=kings[0]),
        C("d4"): c.Piece("W", 2, king=kings[1]),
        C("e3"): c.Piece("W", 3, king=kings[2]),
        C("a7"): c.Piece("B", 4),
    }
    return c.GameState(
        board=before,
        variant=c.GAME1,
        rules_mode=c.CROWNED_MELD_RULES,
        turn="W",
        cooldowns_w=tuple(cooldowns),
        melds_w=tuple(melds),
    )


def test_crowned_meld_requires_at_least_one_king():
    game = forming_position()
    move = game.move_from_notation("e3-f4")
    assert game.meld_options_after(move) == ()
    diagnostics = game.crowned_meld_diagnostics_after(move)
    assert diagnostics[0]["reasons"][0]["code"] == "king_required"


def test_one_king_crownline_scores_15_and_marks_all_three_pieces():
    game = forming_position(kings=(True, False, False))
    move = game.move_from_notation("e3-f4")
    options = game.meld_options_after(move)
    assert len(options) == 1
    assert options[0].points == 15
    assert not options[0].royal

    game = game.apply_move(move)
    assert game.score("W").meld_bonus == 15
    assert game.cooldowns("W") == {1: 3, 2: 3, 3: 3}
    assert options[0].line in game.retired_lines("W")


def test_three_kings_create_royal_crownline_worth_30():
    game = forming_position(kings=(True, True, True))
    meld = game.meld_options_after(game.move_from_notation("e3-f4"))[0]
    assert meld.royal
    assert meld.points == 30

    game = game.apply_notation("e3-f4")
    assert game.score("W").meld_bonus == 30
    assert game.score("W").total == game.score("W").capture_bank + game.score("W").board_value + 30


def test_cooldown_blocks_next_three_turns_by_that_player():
    game = forming_position(kings=(True, False, False)).apply_notation("e3-f4")
    assert game.cooldowns("W") == {1: 3, 2: 3, 3: 3}

    game = game._advance_cooldowns_after_turn("W", None)
    assert game.cooldowns("W") == {1: 2, 2: 2, 3: 2}
    game = game._advance_cooldowns_after_turn("W", None)
    assert game.cooldowns("W") == {1: 1, 2: 1, 3: 1}
    game = game._advance_cooldowns_after_turn("W", None)
    assert game.cooldowns("W") == {}


def test_opponents_turn_does_not_tick_your_cooldown():
    game = forming_position(kings=(True, False, False)).apply_notation("e3-f4")
    before = game.cooldowns("W")
    game = game._advance_cooldowns_after_turn("B", None)
    assert game.cooldowns("W") == before


def test_standing_line_does_not_rescore_when_cooldown_is_clear():
    board = {
        C("b4"): c.Piece("W", 1, king=True),
        C("d4"): c.Piece("W", 2),
        C("f4"): c.Piece("W", 3),
        C("a7"): c.Piece("B", 4),
    }
    game = c.GameState(
        board=board,
        variant=c.GAME1,
        rules_mode=c.CROWNED_MELD_RULES,
        turn="W",
    )
    assert game.eligible_melds_on_board(board, "W", previous_board=board) == ()


def test_scored_line_is_retired_for_that_player_even_after_cooldown():
    retired = c.Meld(("b4", "d4", "f4"), (1, 2, 3), points=15)
    game = forming_position(kings=(True, False, False), melds=(retired,))
    move = game.move_from_notation("e3-f4")
    assert game.meld_options_after(move) == ()
    diagnostics = game.crowned_meld_diagnostics_after(move)
    codes = {reason["code"] for reason in diagnostics[0]["reasons"]}
    assert "retired_line" in codes


def test_same_pieces_may_score_a_different_line_after_cooldown():
    old_meld = c.Meld(("b4", "d4", "f4"), (1, 2, 3), points=15)
    previous = {
        C("b6"): c.Piece("W", 1, king=True),
        C("e5"): c.Piece("W", 2),
        C("e3"): c.Piece("W", 3),
        C("a7"): c.Piece("B", 4),
    }
    rebuilt = dict(previous)
    rebuilt.pop(C("e3"))
    rebuilt[C("f4")] = c.Piece("W", 3)
    game = c.GameState(
        board=previous,
        variant=c.GAME1,
        rules_mode=c.CROWNED_MELD_RULES,
        turn="W",
        melds_w=(old_meld,),
    )

    options = game.eligible_melds_on_board(rebuilt, "W", previous_board=previous)
    assert len(options) == 1
    assert options[0].line == ("b6", "e5", "f4")
    assert options[0].piece_ids == (1, 2, 3)


def test_retirement_is_per_player_not_global():
    line = ("b4", "d4", "f4")
    game = c.GameState(
        board={},
        variant=c.GAME1,
        rules_mode=c.CROWNED_MELD_RULES,
        melds_w=(c.Meld(line, (1, 2, 3)),),
        melds_b=(),
    )
    assert line in game.retired_lines("W")
    assert line not in game.retired_lines("B")


def test_cooldown_prevents_new_line_from_scoring_early_and_explains_why():
    game = forming_position(kings=(True, False, False), cooldowns=((1, 1),))
    move = game.move_from_notation("e3-f4")
    assert game.meld_options_after(move) == ()
    diagnostics = game.crowned_meld_diagnostics_after(move)
    cooldown_reason = next(
        reason
        for reason in diagnostics[0]["reasons"]
        if reason["code"] == "cooldown"
    )
    assert cooldown_reason["pieces"] == [{"piece_id": 1, "turns": 1}]


def test_crowned_profile_persists_into_game_two():
    crownline_set = c.new_set(rules_mode=c.CROWNED_MELD_RULES)
    ended = replace(crownline_set.current_game, game_over=True, end_reason="test")
    crownline_set = replace(crownline_set, current_game=ended).advance_game()
    assert crownline_set.rules_mode == c.CROWNED_MELD_RULES
    assert crownline_set.current_game.rules_mode == c.CROWNED_MELD_RULES
