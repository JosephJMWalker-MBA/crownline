from dataclasses import replace

import pytest

import crownline as c
from crownline_state_notation import (
    CLSN_VERSION,
    canonicalize_clsn,
    clsn_fingerprint,
    parse_clsn,
    serialize_clsn,
)


def C(square):
    return c.alg_to_coord(square)


def test_candidate_game1_start_has_stable_human_readable_notation():
    game = c.GameState.initial(1, rules_mode="candidate")

    assert serialize_clsn(game) == (
        "CLSN1|g=1|r=candidate|t=W|b=0,0|q=-|o=0|e=-|"
        "p=a1:W1,b2:W5,b8:B4,c1:W2,d2:W6,d8:B3,e1:W3,e7:B6,"
        "f8:B2,g1:W4,g7:B5,h8:B1|mw=-|mb=-|cw=-|cb=-"
    )


def test_complex_v11_game2_position_round_trips_exactly():
    game = c.GameState(
        board={
            C("a2"): c.Piece("B", 5),
            C("b3"): c.Piece("B", 4, king=True),
            C("c4"): c.Piece("W", 6, king=True),
            C("c6"): c.Piece("W", 4),
            C("d3"): c.Piece("B", 2),
            C("d7"): c.Piece("W", 5, king=True),
            C("f5"): c.Piece("B", 3, king=True),
        },
        variant=c.GAME2,
        rules_mode="candidate",
        turn="W",
        capture_bank_w=7,
        capture_bank_b=6,
        melds_b=(
            c.Meld(
                line=("g4", "e4", "c4"),
                piece_ids=(3, 4, 2),
                points=15,
                royal=False,
            ),
        ),
        cooldowns_w=((4, 2), (6, 1)),
        cooldowns_b=((3, 3),),
        ply=62,
    )

    text = serialize_clsn(game)
    restored = parse_clsn(text)

    assert restored == replace(game, ply=0)
    assert restored.variant is c.GAME2
    assert "r=candidate" in text
    assert "b=7,6" in text
    assert "c4:W6K" in text
    assert "mb=g4.e4.c4:3.4.2:15:0" in text
    assert "cw=4:2,6:1" in text
    assert "cb=3:3" in text


def test_clsn_is_position_notation_and_deliberately_ignores_ply():
    game = c.GameState.initial(1, rules_mode="candidate")

    assert serialize_clsn(game) == serialize_clsn(replace(game, ply=99))
    assert clsn_fingerprint(game) == clsn_fingerprint(replace(game, ply=99))
    assert clsn_fingerprint(game) != clsn_fingerprint(replace(game, turn="B"))


def test_canonicalization_normalizes_field_board_and_cooldown_order():
    game = c.GameState(
        board={
            C("c3"): c.Piece("W", 2, king=True),
            C("f6"): c.Piece("B", 5),
        },
        variant=c.GAME1,
        rules_mode="candidate",
        turn="B",
        cooldowns_w=((5, 1), (2, 3)),
    )
    canonical = serialize_clsn(game)
    fields = canonical.split("|")
    values = dict(token.split("=", 1) for token in fields[1:])
    noncanonical = "|".join(
        (
            CLSN_VERSION,
            f"p=f6:B5,c3:W2K",
            f"cb={values['cb']}",
            "cw=5:1,2:3",
            f"mb={values['mb']}",
            f"mw={values['mw']}",
            f"e={values['e']}",
            f"o={values['o']}",
            f"q={values['q']}",
            f"b={values['b']}",
            f"t={values['t']}",
            f"r={values['r']}",
            f"g={values['g']}",
        )
    )

    assert canonicalize_clsn(noncanonical) == canonical
    assert "p=c3:W2K,f6:B5" in canonical
    assert "cw=2:3,5:1" in canonical


def test_fingerprint_is_independent_of_python_board_insertion_order():
    first = c.GameState(
        board={
            C("a1"): c.Piece("W", 1),
            C("h8"): c.Piece("B", 6, king=True),
        },
        rules_mode="candidate",
    )
    second = replace(
        first,
        board={
            C("h8"): c.Piece("B", 6, king=True),
            C("a1"): c.Piece("W", 1),
        },
    )

    assert serialize_clsn(first) == serialize_clsn(second)
    assert clsn_fingerprint(first) == clsn_fingerprint(second)
    assert len(clsn_fingerprint(first)) == 64


def test_terminal_status_and_quota_trigger_are_reversible():
    game = c.GameState(
        board={C("a1"): c.Piece("W", 1, king=True)},
        variant=c.GAME1,
        rules_mode="candidate",
        turn="B",
        capture_bank_w=16,
        triggering_player="W",
        game_over=True,
        end_reason="final_response_completed",
    )

    text = serialize_clsn(game)
    restored = parse_clsn(text)

    assert "q=W" in text
    assert "o=1" in text
    assert "e=final_response_completed" in text
    assert restored == game


def test_parser_rejects_states_that_cannot_be_canonical_crownline_positions():
    valid = serialize_clsn(c.GameState.initial(1, rules_mode="candidate"))

    with pytest.raises(ValueError, match="CLSN must begin"):
        parse_clsn(valid.replace("CLSN1", "CLSN2", 1))

    with pytest.raises(ValueError, match="Duplicate piece identity"):
        parse_clsn(valid.replace("p=a1:W1", "p=a1:W1,c3:W1"))

    with pytest.raises(ValueError, match="not playable"):
        parse_clsn(valid.replace("p=a1:W1", "p=a2:W1"))

    with pytest.raises(ValueError, match="Cooldown turns"):
        parse_clsn(valid.replace("cw=-", "cw=1:4"))

    with pytest.raises(ValueError, match="o and e must agree"):
        parse_clsn(valid.replace("o=0", "o=1"))
