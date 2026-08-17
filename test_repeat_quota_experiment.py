from crownline_history_policy_experiment import RepeatAwareEngine
from crownline_position_suite import position_suite
from crownline_repeat_quota_experiment import RepeatQuotaEngine
from crownline_set import CrownlineSet


def _state_for_fixture(fixture) -> CrownlineSet:
    return CrownlineSet(
        first_game_white="A",
        current_game=fixture.game(),
        rules_mode="candidate",
    )


def test_disabling_quota_extension_preserves_repeat_aware_root_policy():
    # Representative Game-1/Game-2 positions are enough to verify composition:
    # with the quota extension disabled, the new engine must reduce to the
    # already-measured repeat-aware policy.
    fixtures = []
    for scenario in position_suite()[:2]:
        fixtures.extend((scenario.game1, scenario.game2))

    for fixture in fixtures:
        state = _state_for_fixture(fixture)
        participant = state.participant_for_color(state.current_game.turn)
        history = RepeatAwareEngine("history-control", depth=3, repeat_penalty=50.0)
        composed = RepeatQuotaEngine(
            "history-plus-quota-control",
            depth=3,
            repeat_penalty=50.0,
            extend_final_response=False,
        )
        assert composed.choose(state, participant).notation == history.choose(state, participant).notation


def test_repeat_quota_engine_exposes_independent_controls():
    engine = RepeatQuotaEngine(
        "controls",
        depth=3,
        repeat_penalty=50.0,
        extend_final_response=True,
    )
    assert engine.repeat_penalty == 50.0
    assert engine.extend_final_response is True
    assert engine.memory_size == 0
    assert engine.extended_leaf_states == 0


def test_repeat_quota_engine_rejects_invalid_configuration():
    for kwargs in ({"depth": 0}, {"repeat_penalty": -1.0}):
        try:
            RepeatQuotaEngine("bad", **kwargs)
        except ValueError:
            pass
        else:
            raise AssertionError(f"invalid configuration should fail: {kwargs}")
