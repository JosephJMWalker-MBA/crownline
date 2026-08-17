import crownline_ai

from crownline_history_policy_experiment import RepeatAwareEngine
from crownline_position_suite import position_suite
from crownline_set import CrownlineSet
from crownline_state_notation import parse_clsn


CYCLE_START = (
    "CLSN1|g=1|r=candidate|t=W|b=6,7|q=-|o=0|e=-|"
    "p=a5:W3,b4:B1K,b6:W6,d4:B3,d6:W5K,g5:B5K,h4:B6|"
    "mw=-|mb=b4.d4.f4:5.3.1:15:0|cw=-|cb=-"
)


def _state(text: str) -> CrownlineSet:
    return CrownlineSet(
        first_game_white="A",
        current_game=parse_clsn(text),
        rules_mode="candidate",
    )


def _apply(state: CrownlineSet, notation: str) -> CrownlineSet:
    game = state.current_game
    move = game.move_from_notation(notation)
    melds = game.meld_options_after(move)
    line = melds[0].line if len(melds) == 1 else None
    return state.apply_move(move, meld_line=line)


def test_zero_repeat_penalty_preserves_baseline_depth3_on_frozen_suite():
    for scenario in position_suite():
        for fixture in (scenario.game1, scenario.game2):
            state = CrownlineSet(
                first_game_white="A",
                current_game=fixture.game(),
                rules_mode="candidate",
            )
            participant = state.participant_for_color(state.current_game.turn)
            engine = RepeatAwareEngine("control", depth=3, repeat_penalty=0)
            decision = engine.choose(state, participant)
            assert (decision.notation, decision.meld_line) == crownline_ai.choose_computer_action(
                state,
                participant=participant,
                depth=3,
            )


def test_repeat_memory_breaks_preserved_cycle_with_large_penalty():
    engine = RepeatAwareEngine("repeat-aware", depth=2, repeat_penalty=1000)
    state0 = _state(CYCLE_START)

    # First traversal: the experimental policy has no history yet, so it follows
    # Baseline A's recorded cycle move and remembers its exact afterstate.
    d0 = engine.choose(state0, "A")
    assert d0.notation == "d6-e5"
    state1 = _apply(state0, d0.notation)
    state2 = _apply(state1, "b4-c3")

    d2 = engine.choose(state2, "A")
    assert d2.notation == "e5-d6"
    state3 = _apply(state2, d2.notation)
    state4 = _apply(state3, "c3-b4")

    # We are back at the exact initial position. Choosing d6-e5 again would
    # recreate the already-produced afterstate, so the sufficiently large test
    # penalty must force a legal escape rather than a second traversal.
    d4 = engine.choose(state4, "A")
    assert d4.notation != "d6-e5"
    assert engine.decisions_with_repeat_candidate >= 1
    assert engine.repeated_action_selected == 0


def test_memory_resets_when_game_ply_resets():
    engine = RepeatAwareEngine("repeat-aware", depth=2, repeat_penalty=100)
    state = _state(CYCLE_START)
    engine.choose(state, "A")
    assert engine.memory_size == 1

    # A separate CLSN fixture begins at ply zero. Since the previous decision
    # was also at ply zero, this is treated as a new-game/scenario boundary and
    # previous repetition memory must not leak into it.
    other = CrownlineSet(
        first_game_white="A",
        current_game=position_suite()[0].game1.game(),
        rules_mode="candidate",
    )
    participant = other.participant_for_color(other.current_game.turn)
    engine.choose(other, participant)
    assert engine.memory_size == 1


def test_negative_repeat_penalty_is_rejected():
    try:
        RepeatAwareEngine("bad", depth=3, repeat_penalty=-1)
    except ValueError as exc:
        assert "repeat_penalty" in str(exc)
    else:
        raise AssertionError("negative repeat penalty should be rejected")
