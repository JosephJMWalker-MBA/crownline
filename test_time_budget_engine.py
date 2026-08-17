from __future__ import annotations

import pytest

from crownline_ai import _actions
from crownline_benchmark import BaselineEngine
from crownline_set import new_set
from crownline_time_engines import choose_computer_action_iterative_baseline


def _candidate_state():
    return new_set(first_game_white="A", rules_mode="candidate")


def _label(notation, meld_line):
    return notation + (f" | {'-'.join(meld_line)}" if meld_line else "")


def test_iterative_completed_depths_match_fixed_baseline_actions_and_nodes():
    state = _candidate_state()
    participant = state.participant_for_color(state.current_game.turn)

    # A frozen clock removes timing noise and lets the semantic-equivalence test
    # exercise all requested depths without changing search behavior.
    notation, meld_line, stats = choose_computer_action_iterative_baseline(
        state,
        participant=participant,
        budget_ms=1.0,
        max_depth=3,
        clock_ns=lambda: 0,
    )

    assert stats.completed_depth == 3
    assert stats.attempted_depth == 3
    assert stats.timed_out is False
    assert [item.depth for item in stats.iterations] == [1, 2, 3]
    assert all(item.completed for item in stats.iterations)

    for item in stats.iterations:
        fixed = BaselineEngine(f"fixed-d{item.depth}", depth=item.depth).choose(
            state,
            participant,
        )
        assert _label(item.notation, item.meld_line) == _label(
            fixed.notation,
            fixed.meld_line,
        )
        assert item.search_nodes == fixed.search_nodes

    fixed_d3 = BaselineEngine("fixed-d3-return", depth=3).choose(state, participant)
    assert _label(notation, meld_line) == _label(fixed_d3.notation, fixed_d3.meld_line)
    assert stats.total_search_nodes == sum(item.search_nodes for item in stats.iterations)


def test_iterative_discards_unfinished_first_depth_and_uses_deterministic_fallback():
    state = _candidate_state()
    participant = state.participant_for_color(state.current_game.turn)

    # First call starts the budget at t=0. Every later check is already beyond
    # the 1 ms deadline, forcing an immediate incomplete depth-1 iteration.
    calls = iter((0, 2_000_000))

    def expired_clock():
        return next(calls, 2_000_000)

    notation, meld_line, stats = choose_computer_action_iterative_baseline(
        state,
        participant=participant,
        budget_ms=1.0,
        max_depth=4,
        clock_ns=expired_clock,
    )

    expected = min(
        (
            move.notation(),
            "-".join(line) if line else "",
            line,
        )
        for move, line in _actions(state)
    )
    assert (notation, meld_line) == (expected[0], expected[2])
    assert stats.completed_depth == 0
    assert stats.attempted_depth == 1
    assert stats.timed_out is True
    assert len(stats.iterations) == 1
    assert stats.iterations[0].completed is False


def test_iterative_budget_validation():
    state = _candidate_state()
    participant = state.participant_for_color(state.current_game.turn)

    with pytest.raises(ValueError, match="budget_ms must be positive"):
        choose_computer_action_iterative_baseline(
            state,
            participant=participant,
            budget_ms=0,
        )

    with pytest.raises(ValueError, match="max_depth must be between 1 and 4"):
        choose_computer_action_iterative_baseline(
            state,
            participant=participant,
            max_depth=5,
        )
