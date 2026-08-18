import pytest

from crownline import new_set
from serve_crownline import _choose_computer_move, _normalize_ai_profile


def _state_after_first_candidate_move():
    state = new_set(first_game_white="A", rules_mode="candidate")
    move = state.current_game.legal_moves()[0]
    return state.apply_move(move)


def test_ai_profile_normalization_preserves_baseline_compatibility():
    assert _normalize_ai_profile(None) == "baseline"
    assert _normalize_ai_profile("computer") == "baseline"
    assert _normalize_ai_profile("standard") == "baseline"
    assert _normalize_ai_profile("strong") == "research"
    assert _normalize_ai_profile("research-strong") == "research"
    with pytest.raises(ValueError):
        _normalize_ai_profile("mystery")


def test_baseline_browser_profile_still_uses_requested_depth():
    state = _state_after_first_candidate_move()
    assert state.participant_for_color(state.current_game.turn) == "B"

    notation, meld_line, evidence = _choose_computer_move(
        state,
        participant="B",
        profile="baseline",
        depth=1,
    )

    assert notation in {move.notation() for move in state.current_game.legal_moves()}
    assert meld_line is None or tuple(meld_line) in state.current_game.meld_options_after(
        state.current_game.move_from_notation(notation)
    )
    assert evidence["profile"] == "baseline"
    assert evidence["depth"] == 1


def test_research_profile_is_restricted_to_v11_candidate_rules():
    state = new_set(first_game_white="A", rules_mode="official")
    with pytest.raises(ValueError, match="validated only for Crownline v1.1"):
        _choose_computer_move(
            state,
            participant="B",
            profile="research",
            depth=2,
        )
