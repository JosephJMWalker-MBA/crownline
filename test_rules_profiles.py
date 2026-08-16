from dataclasses import replace

import crownline as c


def C(square):
    return c.alg_to_coord(square)


def test_official_rules_remain_default():
    game = c.new_game()
    crownline_set = c.new_set()
    assert game.rules_mode == "official"
    assert crownline_set.rules_mode == "official"
    assert crownline_set.current_game.rules_mode == "official"


def test_official_king_remains_bound_by_mandatory_capture():
    game = c.GameState(
        board={
            C("c3"): c.Piece("W", 2, king=True),
            C("d4"): c.Piece("B", 4),
            C("g1"): c.Piece("W", 1),
        },
        variant=c.GAME1,
        rules_mode="official",
        turn="W",
    )
    assert [move.notation() for move in game.legal_moves()] == ["c3xe5"]


def test_sovereign_king_may_decline_capture_but_ordinary_piece_may_not():
    game = c.GameState(
        board={
            C("c3"): c.Piece("W", 2, king=True),
            C("d4"): c.Piece("B", 4),
            C("g1"): c.Piece("W", 1),
        },
        variant=c.GAME1,
        rules_mode="sovereign",
        turn="W",
    )
    moves = {move.notation() for move in game.legal_moves()}

    assert "c3xe5" in moves
    assert {"c3-b2", "c3-d2", "c3-b4"}.issubset(moves)
    assert "g1-f2" not in moves
    assert "g1-h2" not in moves


def test_sovereign_capture_still_requires_complete_multi_jump_sequence():
    game = c.GameState(
        board={
            C("a3"): c.Piece("W", 3, king=True),
            C("b4"): c.Piece("B", 1),
            C("d6"): c.Piece("B", 2),
        },
        variant=c.GAME1,
        rules_mode="sovereign",
        turn="W",
    )
    captures = [move.notation() for move in game.legal_moves() if move.is_capture]
    assert captures == ["a3xc5xe7"]


def test_rules_profile_carries_from_game1_into_game2():
    crownline_set = c.new_set(first_game_white="A", rules_mode="sovereign")
    ended = replace(
        crownline_set.current_game,
        game_over=True,
        end_reason="test_terminal",
    )
    crownline_set = replace(crownline_set, current_game=ended).advance_game()

    assert crownline_set.rules_mode == "sovereign"
    assert crownline_set.game_number == 2
    assert crownline_set.current_game.rules_mode == "sovereign"


def test_invalid_rules_profile_is_rejected():
    try:
        c.new_set(rules_mode="not-a-rule")
    except ValueError as exc:
        assert "rules_mode" in str(exc)
    else:
        raise AssertionError("invalid rules profile should fail")
