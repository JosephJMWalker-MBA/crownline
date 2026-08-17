from __future__ import annotations

from dataclasses import dataclass, field
from math import inf
from time import perf_counter_ns
from typing import Optional

from crownline_ai import _actions
from crownline_benchmark import EngineDecision
from crownline_game import Line
from crownline_rules import Participant
from crownline_set import CrownlineSet
from crownline_state_notation import clsn_fingerprint


@dataclass
class RepeatAwareEngine:
    """Baseline A with a minimal actual-game-history policy at the root.

    The recursive minimax search and static evaluator are unchanged. The only
    experimental addition is a penalty when a candidate root action would
    recreate an exact CLSN game state that this same participant has previously
    produced as one of its own move results in the current game.

    This is intentionally an AI policy, not a Crownline rule. A repeated state
    remains fully legal and can still be chosen when its minimax value is worth
    the configured penalty.
    """

    name: str
    depth: int = 3
    repeat_penalty: float = 100.0
    _game_number: Optional[int] = field(default=None, init=False, repr=False)
    _last_seen_ply: Optional[int] = field(default=None, init=False, repr=False)
    _produced_afterstates: dict[str, int] = field(default_factory=dict, init=False, repr=False)
    repeat_candidates_seen: int = field(default=0, init=False)
    repeated_action_selected: int = field(default=0, init=False)
    decisions_with_repeat_candidate: int = field(default=0, init=False)

    def __post_init__(self) -> None:
        if self.depth < 1 or self.depth > 4:
            raise ValueError("depth must be between 1 and 4")
        if self.repeat_penalty < 0:
            raise ValueError("repeat_penalty must be non-negative")

    @property
    def memory_size(self) -> int:
        return len(self._produced_afterstates)

    def _maybe_reset_for_game(self, state: CrownlineSet) -> None:
        game = state.current_game
        # CLSN fixtures reset raw ply to zero. Ordinary Game 1 -> Game 2 also
        # resets ply. A new benchmark scenario/set likewise starts at ply zero.
        # Within one game this participant only sees monotonically increasing
        # ply values, so a non-increase is a clean reset boundary.
        if (
            self._game_number is None
            or game.variant.number != self._game_number
            or (
                self._last_seen_ply is not None
                and game.ply <= self._last_seen_ply
            )
        ):
            self._game_number = game.variant.number
            self._produced_afterstates.clear()
        self._last_seen_ply = game.ply

    def choose(self, state: CrownlineSet, participant: Participant) -> EngineDecision:
        if state.set_over:
            raise ValueError("Set is already over")
        game = state.current_game
        if game.game_over:
            raise ValueError("Current game is already over")
        if state.participant_for_color(game.turn) != participant:
            raise ValueError(f"It is not Player {participant}'s turn")

        self._maybe_reset_for_game(state)
        actions = _actions(state)
        if not actions:
            raise ValueError("No legal computer move is available")

        started = perf_counter_ns()
        ranked = []
        repeat_candidates = 0
        search_nodes = [0]

        # `crownline_ai._search` recursively resolves the module global, so a
        # temporary wrapper counts every visited node while preserving the exact
        # Baseline A implementation and restoring it immediately afterward.
        import crownline_ai

        original = crownline_ai._search

        def counted(*args, **kwargs):
            search_nodes[0] += 1
            return original(*args, **kwargs)

        crownline_ai._search = counted
        try:
            for move, meld_line in actions:
                child = state.apply_move(move, meld_line=meld_line)
                value = crownline_ai._search(
                    child,
                    participant,
                    max(0, self.depth - 1),
                    -inf,
                    inf,
                )
                fingerprint = clsn_fingerprint(child.current_game)
                repeat_count = self._produced_afterstates.get(fingerprint, 0)
                if repeat_count:
                    repeat_candidates += 1
                adjusted = value - self.repeat_penalty * repeat_count
                line_key = "-".join(meld_line) if meld_line else ""
                ranked.append(
                    (
                        adjusted,
                        value,
                        move.notation(),
                        line_key,
                        meld_line,
                        fingerprint,
                        repeat_count,
                    )
                )
        finally:
            crownline_ai._search = original

        best_adjusted = max(item[0] for item in ranked)
        best = min(
            (item for item in ranked if item[0] == best_adjusted),
            key=lambda item: (item[2], item[3]),
        )

        self.repeat_candidates_seen += repeat_candidates
        self.decisions_with_repeat_candidate += int(repeat_candidates > 0)
        self.repeated_action_selected += int(best[6] > 0)
        self._produced_afterstates[best[5]] = self._produced_afterstates.get(best[5], 0) + 1

        elapsed_ms = (perf_counter_ns() - started) / 1_000_000.0
        return EngineDecision(
            notation=best[2],
            meld_line=best[4],
            elapsed_ms=elapsed_ms,
            search_nodes=search_nodes[0],
            root_actions=len(actions),
        )
