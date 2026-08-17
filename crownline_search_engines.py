from __future__ import annotations

from dataclasses import dataclass
from math import inf
from time import perf_counter_ns
from typing import Optional

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


TTKey = tuple[str, str, Participant, int]


def _tt_key(state: CrownlineSet, participant: Participant, depth: int) -> TTKey:
    """Key one exact search value by canonical position and perspective.

    CLSN1 identifies the game position. `white_participant` is separate because
    CLSN intentionally describes colors rather than the surrounding set's
    Participant A/B mapping. The searching participant and remaining depth are
    also part of minimax value identity.
    """

    return (
        serialize_clsn(state.current_game),
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
) -> float:
    """Alpha-beta search with a conservative exact-value transposition table.

    Only nodes that are fully searched are inserted. A node that terminates via
    alpha-beta cutoff returns the same bound the baseline search would return,
    but that bound is deliberately *not* stored as an exact value. This keeps
    the first transposition experiment semantics-preserving without introducing
    LOWER/UPPER bound bookkeeping.
    """

    key = _tt_key(state, participant, depth)
    cached = cache.get(key)
    if cached is not None:
        stats.cache_hits += 1
        return cached

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


def choose_computer_action_exact_tt(
    state: CrownlineSet,
    participant: Participant = "B",
    *,
    depth: int = 2,
) -> tuple[str, Optional[Line], TranspositionSearchStats]:
    """Choose exactly the Baseline A policy while reusing exact search states."""

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
        )
        line_key = "-".join(meld_line) if meld_line else ""
        ranked.append((value, move.notation(), line_key, meld_line))

    best_value = max(item[0] for item in ranked)
    best = min(
        (item for item in ranked if item[0] == best_value),
        key=lambda item: (item[1], item[2]),
    )
    return best[1], best[3], stats


@dataclass
class ExactTTBaselineEngine:
    """Benchmark adapter for Baseline A + exact transposition caching."""

    name: str
    depth: int = 2
    total_cache_hits: int = 0
    total_expanded_nodes: int = 0
    total_exact_entries: int = 0
    total_cutoff_nodes: int = 0

    def __post_init__(self) -> None:
        if self.depth < 1 or self.depth > 4:
            raise ValueError("ExactTTBaselineEngine depth must be between 1 and 4")

    def choose(self, state: CrownlineSet, participant: Participant) -> EngineDecision:
        root_actions = len(_actions(state))
        started = perf_counter_ns()
        notation, meld_line, stats = choose_computer_action_exact_tt(
            state,
            participant=participant,
            depth=self.depth,
        )
        elapsed_ms = (perf_counter_ns() - started) / 1_000_000.0

        self.total_cache_hits += stats.cache_hits
        self.total_expanded_nodes += stats.expanded_nodes
        self.total_exact_entries += stats.exact_entries
        self.total_cutoff_nodes += stats.cutoff_nodes

        # Baseline benchmark `search_nodes` counts every node that must actually
        # be evaluated/searched. A cache hit avoids that expansion, so TT reports
        # expanded nodes here and exposes hit counts separately on the engine.
        return EngineDecision(
            notation=notation,
            meld_line=meld_line,
            elapsed_ms=elapsed_ms,
            search_nodes=stats.expanded_nodes,
            root_actions=root_actions,
        )
