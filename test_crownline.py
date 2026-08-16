from crownline import GameState, Piece, alg_to_coord, new_game

def C(s):
    return alg_to_coord(s)

def test_opening_moves():
    g = new_game()
    moves = {m.notation() for m in g.legal_moves()}
    assert "d2-e3" in moves
    assert "b2-c3" in moves

def test_mandatory_capture():
    g = GameState(board={
        C("c3"): Piece("W", 2),
        C("d4"): Piece("B", 4),
        C("g1"): Piece("W", 1),
    }, turn="W")
    assert [m.notation() for m in g.legal_moves()] == ["c3xe5"]

def test_multi_jump():
    g = GameState(board={
        C("a3"): Piece("W", 3),
        C("b4"): Piece("B", 1),
        C("d6"): Piece("B", 2),
    }, turn="W")
    assert [m.notation() for m in g.legal_moves()] == ["a3xc5xe7"]

def test_crowning_ends_capture_chain():
    g = GameState(board={
        C("f6"): Piece("W", 5),
        C("g7"): Piece("B", 2),
        C("f8"): Piece("B", 3),
    }, turn="W")
    assert [m.notation() for m in g.legal_moves()] == ["f6xh8"]
    assert g.apply_notation("f6xh8").piece_at("h8").king

def test_king_capture_value_doubles():
    g = GameState(board={
        C("c3"): Piece("W", 1),
        C("d4"): Piece("B", 6, king=True),
    }, turn="W")
    assert g.apply_notation("c3xe5").capture_bank_w == 12

def test_magic_square_meld():
    g = GameState(board={
        C("b6"): Piece("W", 1),
        C("e5"): Piece("W", 2),
        C("f4"): Piece("W", 3),
    }, turn="W")
    s = g.score("W")
    assert s.board_value == 15
    assert s.meld_count == 1
    assert s.meld_bonus == 15
    assert s.total == 30

def test_overlapping_melds_only_score_once():
    # ABC and BEH share d6, so both may be controlled but only one may score.
    g = GameState(board={
        C("b6"): Piece("W", 1),
        C("d6"): Piece("W", 2),
        C("f6"): Piece("W", 3),
        C("e5"): Piece("W", 4),
        C("d4"): Piece("W", 5),
    }, turn="W")
    assert len(g.controlled_crownlines("W")) == 2
    assert len(g.scoring_melds("W")) == 1

def test_quota_gives_one_response():
    g = GameState(
        board={
            C("c3"): Piece("W", 1),
            C("d4"): Piece("B", 6),
            C("g7"): Piece("B", 5),
            C("a1"): Piece("W", 2),
        },
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
