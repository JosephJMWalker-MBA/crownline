from dataclasses import replace

import crownline as c


def C(square):
    return c.alg_to_coord(square)


def sovereign_position(mode):
    return c.GameState(
        board={
            C("c3"): c.Piece("W", 2, king=True),
            C("d4"): c.Piece("B", 4),
            C("g1"): c.Piece("W", 1),
        },
        variant=c.GAME1,
        rules_mode=mode,
        turn="W",
    )


def crowned_position(mode, *, king=True, melds=()):
    return c.GameState(
        board={
            C("b4"): c.Piece("W", 1, king=king),
            C("d4"): c.Piece("W", 2),
            C("e3"): c.Piece("W", 3),
            C("a7"): c.Piece("B", 4),
        },
        variant=c.GAME1,
        rules_mode=mode,
        turn="W",
        melds_w=melds,
    )


def test_candidate_profile_is_available_and_labeled():
    game = c.new_game(rules_mode="candidate")
    crownline_set = c.new_set(rules_mode="candidate")
    assert game.rules_mode == c.V1_1_CANDIDATE_RULES
    assert crownline_set.rules_mode == c.V1_1_CANDIDATE_RULES
    assert c.rules_mode_label(c.V1_1_CANDIDATE_RULES) == "Experimental Crownline v1.1 Candidate"


def test_candidate_king_is_sovereign():
    game = sovereign_position("candidate")
    moves = {move.notation() for move in game.legal_moves()}
    assert "c3xe5" in moves
    assert {"c3-b2", "c3-d2", "c3-b4"}.issubset(moves)
    assert "g1-f2" not in moves
    assert "g1-h2" not in moves


def test_crowned_only_profile_remains_capture_bound():
    game = sovereign_position("crowned")
    assert [move.notation() for move in game.legal_moves()] == ["c3xe5"]


def test_candidate_requires_a_king_for_crownline():
    game = crowned_position("candidate", king=False)
    move = game.move_from_notation("e3-f4")
    assert game.meld_options_after(move) == ()


def test_candidate_scores_crowned_meld_and_applies_cooldown():
    game = crowned_position("candidate", king=True)
    game = game.apply_notation("e3-f4")
    assert game.score("W").meld_bonus == 15
    assert game.cooldowns("W") == {1: 3, 2: 3, 3: 3}
    assert game.variant.crown_lines[2] in game.retired_lines("W")


def test_candidate_retires_scored_line_for_that_player():
    line = c.GAME1.crown_lines[2]
    old_meld = c.Meld(line=line, piece_ids=(1, 2, 3), points=15)
    game = crowned_position("candidate", king=True, melds=(old_meld,))
    move = game.move_from_notation("e3-f4")
    assert game.meld_options_after(move) == ()
    diagnostics = game.crowned_meld_diagnostics_after(move)
    assert diagnostics
    assert any(reason["code"] == "retired_line" for reason in diagnostics[0]["reasons"])


def test_candidate_profile_carries_into_game_two():
    crownline_set = c.new_set(first_game_white="A", rules_mode="candidate")
    ended = replace(
        crownline_set.current_game,
        game_over=True,
        end_reason="test_terminal",
    )
    crownline_set = replace(crownline_set, current_game=ended).advance_game()
    assert crownline_set.rules_mode == "candidate"
    assert crownline_set.current_game.rules_mode == "candidate"


def test_sovereign_only_keeps_official_meld_semantics():
    game = crowned_position("sovereign", king=False)
    move = game.move_from_notation("e3-f4")
    options = game.meld_options_after(move)
    assert len(options) == 1
    assert options[0].points == 15
