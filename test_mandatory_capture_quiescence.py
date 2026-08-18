from crownline_human_decision_suite import human_decision_suite
from crownline_mandatory_capture_quiescence_experiment import (
    MandatoryCaptureQuiescenceEngine,
    mandatory_capture_actions,
)
from crownline_promotion_maturity_experiment import PromotionMaturityEngine
from crownline_set import CrownlineSet, new_set
from crownline_state_notation import parse_clsn


def test_initial_position_is_not_a_quiescence_capture_node():
    state = new_set(rules_mode="candidate")
    assert mandatory_capture_actions(state) == ()


def test_sovereign_king_capture_is_not_mandatory_quiescence():
    # This is the recorded position after b2xd4. Black's King on e3 can make
    # e3xc5xa7, but v1.1 Sovereignty releases the whole turn from mandatory
    # capture whenever a King has a capture. The compound capture is therefore
    # legal, not forced, and must not be extended by *mandatory*-capture
    # quiescence.
    state = CrownlineSet(
        first_game_white="A",
        current_game=parse_clsn(
            "CLSN1|g=1|r=candidate|t=B|b=15,5|q=W|o=0|e=-|p=b6:W6K,c1:W2,d4:W1,e3:B6K,e7:W3K,f6:W4K|mw=-|mb=-|cw=-|cb=-"
        ),
        rules_mode="candidate",
    )
    legal = state.current_game.legal_moves()
    assert any(move.notation() == "e3xc5xa7" for move in legal)
    assert any(not move.is_capture for move in legal)
    assert mandatory_capture_actions(state) == ()


def test_ordinary_piece_capture_is_visible_to_mandatory_quiescence():
    # In this small candidate-rules position only the ordinary Black piece on
    # c5 can capture. No Black King has a capture, so Sovereignty cannot release
    # the obligation and the turn is genuinely capture-forced.
    state = CrownlineSet(
        first_game_white="A",
        current_game=parse_clsn(
            "CLSN1|g=1|r=candidate|t=B|b=0,0|q=-|o=0|e=-|p=b4:W1,c5:B2|mw=-|mb=-|cw=-|cb=-"
        ),
        rules_mode="candidate",
    )
    actions = mandatory_capture_actions(state)
    assert len(actions) == 1
    assert actions[0][0].is_capture
    assert actions[0][0].notation() == "c5xa3"


def test_qdepth_zero_is_exact_promotion_maturity_control():
    fixture = next(
        fixture
        for fixture in human_decision_suite()
        if fixture.bucket == "bot-crownline-construction"
    )
    state = fixture.state()
    control = PromotionMaturityEngine("control", depth=3, maturity_weight=10.0).choose(
        state,
        fixture.participant,
    )
    q0 = MandatoryCaptureQuiescenceEngine(
        "q0",
        depth=3,
        maturity_weight=10.0,
        qdepth=0,
    ).choose(state, fixture.participant)
    assert (q0.notation, q0.meld_line) == (control.notation, control.meld_line)
