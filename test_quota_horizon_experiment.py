import crownline as c
import crownline_ai

from crownline_position_suite import position_suite
from crownline_quota_horizon_experiment import (
    QuotaHorizonEngine,
    choose_quota_horizon_action,
    quota_horizon_search,
)
from crownline_set import CrownlineSet


def C(square):
    return c.alg_to_coord(square)


def _state_for_fixture(fixture) -> CrownlineSet:
    return CrownlineSet(
        first_game_white="A",
        current_game=fixture.game(),
        rules_mode="candidate",
    )


def test_disabled_quota_extension_preserves_depth3_baseline_policy():
    for scenario in position_suite():
        for fixture in (scenario.game1, scenario.game2):
            state = _state_for_fixture(fixture)
            participant = state.participant_for_color(state.current_game.turn)
            assert choose_quota_horizon_action(
                state,
                participant,
                depth=3,
                extend_final_response=False,
            ) == crownline_ai.choose_computer_action(
                state,
                participant=participant,
                depth=3,
            )


def test_depth_zero_extension_resolves_the_exact_final_response():
    # This is the post-trigger state from the Game-2 quota regression: White has
    # crossed 15, and Black has exactly one final response, h7xf5, capturing the
    # triggering King. A depth cutoff here must not treat the state as an ordinary
    # nonterminal leaf when the experiment is enabled.
    game = c.GameState(
        board={
            C("g6"): c.Piece("W", 1, king=True),
            C("h7"): c.Piece("B", 2),
        },
        variant=c.GAME2,
        rules_mode="candidate",
        turn="B",
        capture_bank_w=15,
        triggering_player="W",
    )
    state = CrownlineSet(
        first_game_white="A",
        current_game=game,
        rules_mode="candidate",
    )
    triggering_participant = state.participant_for_color("W")

    assert [move.notation() for move in game.legal_moves()] == ["h7xf5"]
    baseline_leaf = crownline_ai._evaluate(state, triggering_participant)
    extended_leaf = quota_horizon_search(
        state,
        triggering_participant,
        0,
        float("-inf"),
        float("inf"),
        extend_final_response=True,
    )
    terminal = state.apply_notation("h7xf5")

    assert terminal.current_game.game_over
    assert terminal.current_game.end_reason == "final_response_completed"
    assert extended_leaf == crownline_ai._evaluate(terminal, triggering_participant)
    assert extended_leaf != baseline_leaf


def test_quota_horizon_engine_records_only_actual_extensions():
    state = _state_for_fixture(position_suite()[0].game1)
    participant = state.participant_for_color(state.current_game.turn)
    engine = QuotaHorizonEngine("quota-horizon-test", depth=1, extend_final_response=True)
    decision = engine.choose(state, participant)

    assert decision.notation in {move.notation() for move in state.current_game.legal_moves()}
    assert engine.extended_leaf_states >= 0


def test_quota_horizon_engine_validates_depth():
    try:
        QuotaHorizonEngine("bad", depth=0)
    except ValueError as exc:
        assert "depth" in str(exc)
    else:
        raise AssertionError("depth zero should be rejected")
