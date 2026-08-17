from __future__ import annotations

from dataclasses import dataclass
from math import inf
from time import perf_counter_ns
from typing import Callable, Hashable, Optional

from crownline_ai import _actions, _evaluate
from crownline_benchmark import EngineDecision
from crownline_game import Line
from crownline_rules import Participant
from crownline_set import CrownlineSet
from crownline_state_notation import serialize_clsn


@dataclass
class TranspositionSearchStats:
    """Per-decision measurements for exact transposition caching."""

    expanded_nodes: int = 0
    cache_hits: int = 0
    exact_entries: int = 0
    cutoff_nodes: int = 0

    @property
    def probes(self) -> int:
        return self.expanded_nodes + self.cache_hits

    @property
    def hit_rate(self) -> float:
        return self.cache_hits / self.probes if self.probes else 0.0


TTKey = Hashable
KeyBuilder = Callable[[CrownlineSet, Participant, int], TTKey]


def _tt_key(state: CrownlineSet, participant: Participant, depth: int) -> TTKey:
    """Reference key using canonical CLSN1 text plus search perspective."""

    return (
        serialize_clsn(state.current_game),
        state.white_participant,
        participant,
        depth,
    )


def _structural_game_identity(state: CrownlineSet) -> tuple:
    """Return the same future-relevant facts encoded by CLSN1 without text I/O.

    This is deliberately an *internal search key*, not a replacement for CLSN1.
    CLSN remains the reversible external notation and benchmark-fixture format.
    The structural tuple exists only to test whether avoiding repeated string
    materialization makes exact transposition caching computationally worthwhile.
    """

    game = state.current_game
    pieces = tuple(
        sorted(
            (
                position[0],
                position[1],
                piece.owner,
                piece.value,
                bool(piece.king),
            )
            for position, piece in game.board.items()
        )
    )

    def meld_identity(meld) -> tuple:
        return (
            tuple(meld.line),
            tuple(meld.piece_ids),
            meld.points,
            bool(meld.royal),
        )

    return (
        game.variant.number,
        game.rules_mode,
        game.turn,
        game.capture_bank_w,
        game.capture_bank_b,
        game.triggering_player,
        bool(game.game_over),
        game.end_reason,
        pieces,
        tuple(sorted(meld_identity(meld) for meld in game.melds_w)),
        tuple(sorted(meld_identity(meld) for meld in game.melds_b)),
        tuple(sorted(game.cooldowns_w)),
        tuple(sorted(game.cooldowns_b)),
    )


def _structural_tt_key(
    state: CrownlineSet,
    participant: Participant,
    depth: int,
) -> TTKey:
    """CLSN-equivalent structural key without serializing canonical text."""

    return (
        _structural_game_identity(state),
        state.white_participant,
        participant,
        depth,
    )


def _search_exact_tt(
    state: CrownlineSet,
    participant: Participant,
    depth: int,
    alpha: float,
    beta: float,
    cache: dict[TTKey, float],
    stats: TranspositionSearchStats,
    key_builder: KeyBuilder,
) -> float:
    """Alpha-beta search with a conservative exact-value transposition table.

    Only nodes that are fully searched are inserted. A node that terminates via
    alpha-beta cutoff returns the same bound the baseline search would return,
    but that bound is deliberately *not* stored as an exact value. This keeps
    transposition experiments semantics-preserving without introducing
    LOWER/UPPER bound bookkeeping.
    """

    key = key_builder(state, participant, depth)
    if key in cache:
        stats.cache_hits += 1
        return cache[key]

    stats.expanded_nodes += 1
    game = state.current_game
    if depth <= 0 or game.game_over:
        value = _evaluate(state, participant)
        cache[key] = value
        stats.exact_entries += 1
        return value

    actions = _actions(state)
    if not actions:
        value = _evaluate(state, participant)
        cache[key] = value
        stats.exact_entries += 1
        return value

    maximizing = state.participant_for_color(game.turn) == participant
    cutoff = False

    if maximizing:
        value = -inf
        for move, meld_line in actions:
            child = state.apply_move(move, meld_line=meld_line)
            value = max(
                value,
                _search_exact_tt(
                    child,
                    participant,
                    depth - 1,
                    alpha,
                    beta,
                    cache,
                    stats,
                    key_builder,
                ),
            )
            alpha = max(alpha, value)
            if alpha >= beta:
                cutoff = True
                stats.cutoff_nodes += 1
                break
    else:
        value = inf
        for move, meld_line in actions:
            child = state.apply_move(move, meld_line=meld_line)
            value = min(
                value,
                _search_exact_tt(
                    child,
                    participant,
                    depth - 1,
                    alpha,
                    beta,
                    cache,
                    stats,
                    key_builder,
                ),
            )
            beta = min(beta, value)
            if alpha >= beta:
                cutoff = True
                stats.cutoff_nodes += 1
                break

    if not cutoff:
        cache[key] = value
        stats.exact_entries += 1
    return value


def _choose_exact_tt(
    state: CrownlineSet,
    participant: Participant,
    *,
    depth: int,
    key_builder: KeyBuilder,
) -> tuple[str, Optional[Line], TranspositionSearchStats]:
    if depth < 1 or depth > 4:
        raise ValueError("Transposition search depth must be between 1 and 4")
    if state.set_over:
        raise ValueError("Set is already over")
    game = state.current_game
    if game.game_over:
        raise ValueError("Current game is already over")
    if state.participant_for_color(game.turn) != participant:
        raise ValueError(f"It is not Player {participant}'s turn")

    actions = _actions(state)
    if not actions:
        raise ValueError("No legal computer move is available")

    cache: dict[TTKey, float] = {}
    stats = TranspositionSearchStats()
    ranked = []
    for move, meld_line in actions:
        child = state.apply_move(move, meld_line=meld_line)
        value = _search_exact_tt(
            child,
            participant,
            max(0, depth - 1),
            -inf,
            inf,
            cache,
            stats,
            key_builder,
        )
        line_key = "-".join(meld_line) if meld_line else ""
        ranked.append((value, move.notation(), line_key, meld_line))

    best_value = max(item[0] for item in ranked)
    best = min(
        (item for item in ranked if item[0] == best_value),
        key=lambda item: (item[1], item[2]),
    )
    return best[1], best[3], stats


def choose_computer_action_exact_tt(
    state: CrownlineSet,
    participant: Participant = "B",
    *,
    depth: int = 2,
) -> tuple[str, Optional[Line], TranspositionSearchStats]:
    """Choose Baseline A's policy using canonical CLSN1 text as the TT key."""

    return _choose_exact_tt(
        state,
        participant,
        depth=depth,
        key_builder=_tt_key,
    )


def choose_computer_action_structural_tt(
    state: CrownlineSet,
    participant: Participant = "B",
    *,
    depth: int = 2,
) -> tuple[str, Optional[Line], TranspositionSearchStats]:
    """Choose the same policy using the CLSN-equivalent structural TT key."""

    return _choose_exact_tt(
        state,
        participant,
        depth=depth,
        key_builder=_structural_tt_key,
    )


@dataclass
class _ExactTTAdapter:
    name: str
    depth: int = 2
    total_cache_hits: int = 0
    total_expanded_nodes: int = 0
    total_exact_entries: int = 0
    total_cutoff_nodes: int = 0

    def __post_init__(self) -> None:
        if self.depth < 1 or self.depth > 4:
            raise ValueError("Transposition engine depth must be between 1 and 4")

    def _choose_with_stats(
        self,
        state: CrownlineSet,
        participant: Participant,
    ) -> tuple[str, Optional[Line], TranspositionSearchStats]:
        raise NotImplementedError

    def choose(self, state: CrownlineSet, participant: Participant) -> EngineDecision:
        root_actions = len(_actions(state))
        started = perf_counter_ns()
        notation, meld_line, stats = self._choose_with_stats(state, participant)
        elapsed_ms = (perf_counter_ns() - started) / 1_000_000.0

        self.total_cache_hits += stats.cache_hits
        self.total_expanded_nodes += stats.expanded_nodes
        self.total_exact_entries += stats.exact_entries
        self.total_cutoff_nodes += stats.cutoff_nodes

        return EngineDecision(
            notation=notation,
            meld_line=meld_line,
            elapsed_ms=elapsed_ms,
            search_nodes=stats.expanded_nodes,
            root_actions=root_actions,
        )


@dataclass
class ExactTTBaselineEngine(_ExactTTAdapter):
    """Baseline A + exact TT keyed by canonical CLSN1 text."""

    def _choose_with_stats(
        self,
        state: CrownlineSet,
        participant: Participant,
    ) -> tuple[str, Optional[Line], TranspositionSearchStats]:
        return choose_computer_action_exact_tt(
            state,
            participant=participant,
            depth=self.depth,
        )


@dataclass
class ExactStructuralTTBaselineEngine(_ExactTTAdapter):
    """Baseline A + exact TT keyed by a CLSN-equivalent structural tuple."""

    def _choose_with_stats(
        self,
        state: CrownlineSet,
        participant: Participant,
    ) -> tuple[str, Optional[Line], TranspositionSearchStats]:
        return choose_computer_action_structural_tt(
            state,
            participant=participant,
            depth=self.depth,
        )
