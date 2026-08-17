from __future__ import annotations

import argparse
import hashlib
import json
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from pathlib import Path
from statistics import mean
from time import perf_counter_ns
from typing import Optional, Protocol, Tuple

import crownline_ai
from crownline_game import Line, Move
from crownline_rules import Participant, RulesMode, coord_to_alg, normalize_rules_mode
from crownline_set import CrownlineSet, new_set


ROOT = Path(__file__).resolve().parent
REPORT_SCHEMA_VERSION = 2


@dataclass(frozen=True)
class EngineDecision:
    notation: str
    meld_line: Optional[Line]
    elapsed_ms: float
    search_nodes: int
    root_actions: int


class BenchmarkEngine(Protocol):
    name: str

    def choose(self, state: CrownlineSet, participant: Participant) -> EngineDecision:
        ...


@contextmanager
def _count_baseline_search_nodes():
    """Count calls into the existing baseline search without changing its logic.

    `crownline_ai._search` recursively resolves its own module global, so wrapping
    that symbol counts every visited search node while the original function
    remains authoritative. The wrapper is restored immediately after a choice.
    Benchmark runs are intentionally single-threaded.
    """

    original = crownline_ai._search
    counter = {"nodes": 0}

    def counted(*args, **kwargs):
        counter["nodes"] += 1
        return original(*args, **kwargs)

    crownline_ai._search = counted
    try:
        yield counter
    finally:
        crownline_ai._search = original


def _actions(state: CrownlineSet) -> Tuple[tuple[Move, Optional[Line]], ...]:
    """Enumerate legal move + Crownline-choice actions for benchmark analysis."""

    actions = []
    game = state.current_game
    for move in game.legal_moves():
        melds = game.meld_options_after(move)
        if len(melds) > 1:
            actions.extend((move, meld.line) for meld in melds)
        else:
            actions.append((move, melds[0].line if melds else None))
    return tuple(actions)


def _root_action_count(state: CrownlineSet) -> int:
    """Count move + Crownline-choice actions at the root position."""

    return len(_actions(state))


@dataclass(frozen=True)
class BaselineEngine:
    """Adapter around the existing deterministic Crownline computer opponent."""

    name: str
    depth: int = 2

    def __post_init__(self) -> None:
        if self.depth < 1 or self.depth > 4:
            raise ValueError("BaselineEngine depth must be between 1 and 4")

    def choose(self, state: CrownlineSet, participant: Participant) -> EngineDecision:
        root_actions = _root_action_count(state)
        started = perf_counter_ns()
        with _count_baseline_search_nodes() as counter:
            notation, meld_line = crownline_ai.choose_computer_action(
                state,
                participant=participant,
                depth=self.depth,
            )
        elapsed_ms = (perf_counter_ns() - started) / 1_000_000.0
        return EngineDecision(
            notation=notation,
            meld_line=meld_line,
            elapsed_ms=elapsed_ms,
            search_nodes=counter["nodes"],
            root_actions=root_actions,
        )


@dataclass
class ParticipantMetrics:
    decisions: int = 0
    elapsed_ms: float = 0.0
    search_nodes: int = 0
    root_actions: int = 0
    capture_points: int = 0
    promotions: int = 0
    crownlines_scored: int = 0
    sovereign_opportunities: int = 0
    sovereign_refusals: int = 0
    quota_triggers: int = 0
    final_response_moves: int = 0
    max_decision_ms: float = 0.0
    max_search_nodes: int = 0

    def record_decision(self, decision: EngineDecision) -> None:
        self.decisions += 1
        self.elapsed_ms += decision.elapsed_ms
        self.search_nodes += decision.search_nodes
        self.root_actions += decision.root_actions
        self.max_decision_ms = max(self.max_decision_ms, decision.elapsed_ms)
        self.max_search_nodes = max(self.max_search_nodes, decision.search_nodes)

    def absorb(self, other: "ParticipantMetrics") -> None:
        self.decisions += other.decisions
        self.elapsed_ms += other.elapsed_ms
        self.search_nodes += other.search_nodes
        self.root_actions += other.root_actions
        self.capture_points += other.capture_points
        self.promotions += other.promotions
        self.crownlines_scored += other.crownlines_scored
        self.sovereign_opportunities += other.sovereign_opportunities
        self.sovereign_refusals += other.sovereign_refusals
        self.quota_triggers += other.quota_triggers
        self.final_response_moves += other.final_response_moves
        self.max_decision_ms = max(self.max_decision_ms, other.max_decision_ms)
        self.max_search_nodes = max(self.max_search_nodes, other.max_search_nodes)


@dataclass(frozen=True)
class MoveTrace:
    ply: int
    participant: Participant
    color: str
    notation: str
    meld_line: Optional[Line]
    sovereign_opportunity: bool
    sovereign_refusal: bool
    state_before: str
    state_after: str


@dataclass(frozen=True)
class FirstRepeatObservation:
    fingerprint: str
    first_seen_ply: int
    repeated_ply: int


@dataclass(frozen=True)
class EscapeOpportunity:
    ply: int
    participant: Participant
    color: str
    legal_actions: int
    escape_actions: int
    escape_action_examples: Tuple[str, ...]


@dataclass(frozen=True)
class RepetitionDiagnostic:
    fingerprint: str
    occurrence_count: int
    first_seen_ply: int
    first_repeat_ply: int
    previous_seen_ply: int
    detected_ply: int
    cycle_length: int
    first_repeat_observed: FirstRepeatObservation
    repeated_state: dict
    cycle_moves: Tuple[MoveTrace, ...]
    sovereign_in_cycle: bool
    sovereign_refusals_in_cycle: int
    escape_opportunities: Tuple[EscapeOpportunity, ...]
    positions_with_escape_actions: int
    escape_actions: int
    escape_action_examples: Tuple[str, ...]


@dataclass(frozen=True)
class GameRecord:
    game_number: int
    white_participant: Participant
    black_participant: Participant
    complete: bool
    winner: Optional[str]
    end_reason: str
    plies: int
    white_score: int
    black_score: int
    score_a: int
    score_b: int
    capture_bank_w: int
    capture_bank_b: int
    melds_w: int
    melds_b: int
    metrics_a: ParticipantMetrics
    metrics_b: ParticipantMetrics
    repetition: Optional[RepetitionDiagnostic] = None


@dataclass(frozen=True)
class SetRecord:
    pair_index: int
    leg: str
    first_game_white: Participant
    complete: bool
    winner: Optional[str]
    aggregate_a: int
    aggregate_b: int
    capped_game: Optional[int]
    games: Tuple[GameRecord, ...]


@dataclass(frozen=True)
class BenchmarkReport:
    schema_version: int
    rules_mode: RulesMode
    pairs: int
    sets_per_pair: int
    max_game_plies: int
    repetition_limit: int
    deterministic: bool
    engine_a: dict
    engine_b: dict
    source_fingerprints: dict
    summary: dict
    sets: Tuple[SetRecord, ...]


def _source_fingerprint(*relative_paths: str) -> str:
    digest = hashlib.sha256()
    for relative_path in relative_paths:
        path = ROOT / relative_path
        digest.update(relative_path.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _sovereign_opportunity(game) -> bool:
    """True when a King capture exists and Sovereignty exposes a non-capture."""

    legal = game.legal_moves()
    if not any(not move.is_capture for move in legal):
        return False
    for move in legal:
        if not move.is_capture:
            continue
        piece = game.board.get(move.path[0])
        if piece is not None and piece.king:
            return True
    return False


def _canonical_meld(meld) -> tuple:
    return (
        tuple(meld.line),
        tuple(meld.piece_ids),
        meld.points,
        bool(meld.royal),
    )


def _canonical_game_state(game) -> dict:
    """Return the complete future-relevant game state, excluding only ply count.

    Excluding `ply` lets the harness recognize a semantically identical position
    reached at different times. Everything that can alter legal moves, scoring,
    cooldown/retirement behavior, or terminal status remains in the fingerprint.
    """

    pieces = [
        (coord_to_alg(position), piece.owner, piece.value, bool(piece.king))
        for position, piece in sorted(
            game.board.items(),
            key=lambda item: coord_to_alg(item[0]),
        )
    ]
    return {
        "variant": game.variant.number,
        "rules_mode": game.rules_mode,
        "turn": game.turn,
        "capture_bank_w": game.capture_bank_w,
        "capture_bank_b": game.capture_bank_b,
        "melds_w": sorted(_canonical_meld(meld) for meld in game.melds_w),
        "melds_b": sorted(_canonical_meld(meld) for meld in game.melds_b),
        "cooldowns_w": list(game.cooldowns_w),
        "cooldowns_b": list(game.cooldowns_b),
        "triggering_player": game.triggering_player,
        "game_over": bool(game.game_over),
        "end_reason": game.end_reason,
        "pieces": pieces,
    }


def _game_state_fingerprint(game) -> str:
    packed = json.dumps(
        _canonical_game_state(game),
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(packed).hexdigest()


def _action_label(move: Move, meld_line: Optional[Line]) -> str:
    if meld_line is None:
        return move.notation()
    return f"{move.notation()} | meld {'-'.join(meld_line)}"


def _escape_opportunities(
    states_by_ply: dict[int, CrownlineSet],
    *,
    start_ply: int,
    end_ply: int,
    cycle_fingerprints: set[str],
) -> Tuple[EscapeOpportunity, ...]:
    """Measure legal deviations from every decision state inside a detected cycle."""

    observations = []
    for ply in range(start_ply, end_ply):
        state = states_by_ply.get(ply)
        if state is None or state.current_game.game_over:
            continue
        actions = _actions(state)
        escapes = []
        for move, meld_line in actions:
            child = state.apply_move(move, meld_line=meld_line)
            if _game_state_fingerprint(child.current_game) not in cycle_fingerprints:
                escapes.append(_action_label(move, meld_line))
        observations.append(
            EscapeOpportunity(
                ply=ply,
                participant=state.participant_for_color(state.current_game.turn),
                color=state.current_game.turn,
                legal_actions=len(actions),
                escape_actions=len(escapes),
                escape_action_examples=tuple(escapes[:8]),
            )
        )
    return tuple(observations)


@dataclass
class RepetitionTracker:
    """Observe exact game-state recurrence without changing Crownline rules."""

    limit: int = 3
    seen: dict[str, list[int]] = field(default_factory=dict)
    history: list[MoveTrace] = field(default_factory=list)
    states_by_ply: dict[int, CrownlineSet] = field(default_factory=dict)
    first_repeat: Optional[FirstRepeatObservation] = None

    @classmethod
    def start(cls, state: CrownlineSet, limit: int = 3) -> "RepetitionTracker":
        if limit != 0 and limit < 2:
            raise ValueError("repetition_limit must be 0 (disabled) or at least 2")
        tracker = cls(limit=limit)
        fingerprint = _game_state_fingerprint(state.current_game)
        tracker.seen[fingerprint] = [state.current_game.ply]
        tracker.states_by_ply[state.current_game.ply] = state
        return tracker

    def observe(
        self,
        before: CrownlineSet,
        after: CrownlineSet,
        *,
        participant: Participant,
        move: Move,
        meld_line: Optional[Line],
        sovereign_opportunity: bool,
    ) -> Optional[RepetitionDiagnostic]:
        before_fp = _game_state_fingerprint(before.current_game)
        after_fp = _game_state_fingerprint(after.current_game)
        trace = MoveTrace(
            ply=after.current_game.ply,
            participant=participant,
            color=before.current_game.turn,
            notation=move.notation(),
            meld_line=meld_line,
            sovereign_opportunity=sovereign_opportunity,
            sovereign_refusal=sovereign_opportunity and not move.is_capture,
            state_before=before_fp,
            state_after=after_fp,
        )
        self.history.append(trace)
        self.states_by_ply[after.current_game.ply] = after

        occurrences = self.seen.setdefault(after_fp, [])
        occurrences.append(after.current_game.ply)
        if len(occurrences) == 2 and self.first_repeat is None:
            self.first_repeat = FirstRepeatObservation(
                fingerprint=after_fp,
                first_seen_ply=occurrences[0],
                repeated_ply=occurrences[1],
            )

        if self.limit == 0 or len(occurrences) < self.limit or after.current_game.game_over:
            return None

        previous_ply = occurrences[-2]
        detected_ply = occurrences[-1]
        cycle_moves = tuple(
            trace
            for trace in self.history
            if previous_ply < trace.ply <= detected_ply
        )
        cycle_fingerprints = {after_fp}
        for trace in cycle_moves:
            cycle_fingerprints.add(trace.state_before)
            cycle_fingerprints.add(trace.state_after)

        escape_opportunities = _escape_opportunities(
            self.states_by_ply,
            start_ply=previous_ply,
            end_ply=detected_ply,
            cycle_fingerprints=cycle_fingerprints,
        )
        escape_count = sum(item.escape_actions for item in escape_opportunities)
        escape_examples = tuple(
            f"ply {item.ply}: {example}"
            for item in escape_opportunities
            for example in item.escape_action_examples
        )[:12]
        first_repeat = self.first_repeat or FirstRepeatObservation(
            fingerprint=after_fp,
            first_seen_ply=occurrences[0],
            repeated_ply=occurrences[1],
        )
        return RepetitionDiagnostic(
            fingerprint=after_fp,
            occurrence_count=len(occurrences),
            first_seen_ply=occurrences[0],
            first_repeat_ply=occurrences[1],
            previous_seen_ply=previous_ply,
            detected_ply=detected_ply,
            cycle_length=detected_ply - previous_ply,
            first_repeat_observed=first_repeat,
            repeated_state=_canonical_game_state(after.current_game),
            cycle_moves=cycle_moves,
            sovereign_in_cycle=any(trace.sovereign_opportunity for trace in cycle_moves),
            sovereign_refusals_in_cycle=sum(
                trace.sovereign_refusal for trace in cycle_moves
            ),
            escape_opportunities=escape_opportunities,
            positions_with_escape_actions=sum(
                item.escape_actions > 0 for item in escape_opportunities
            ),
            escape_actions=escape_count,
            escape_action_examples=escape_examples,
        )


def _game_record(
    state: CrownlineSet,
    metrics: dict[Participant, ParticipantMetrics],
    *,
    complete: bool,
    end_reason: Optional[str] = None,
    repetition: Optional[RepetitionDiagnostic] = None,
) -> GameRecord:
    game = state.current_game
    white_score = game.score("W").total
    black_score = game.score("B").total
    if state.white_participant == "A":
        score_a, score_b = white_score, black_score
    else:
        score_a, score_b = black_score, white_score

    winner: Optional[str]
    if complete:
        winner = "A" if score_a > score_b else "B" if score_b > score_a else "DRAW"
    else:
        winner = None

    return GameRecord(
        game_number=game.variant.number,
        white_participant=state.white_participant,
        black_participant=state.black_participant,
        complete=complete,
        winner=winner,
        end_reason=end_reason or game.end_reason or "unknown",
        plies=game.ply,
        white_score=white_score,
        black_score=black_score,
        score_a=score_a,
        score_b=score_b,
        capture_bank_w=game.capture_bank_w,
        capture_bank_b=game.capture_bank_b,
        melds_w=len(game.melds_w),
        melds_b=len(game.melds_b),
        metrics_a=metrics["A"],
        metrics_b=metrics["B"],
        repetition=repetition,
    )


def _incomplete_set_record(
    *,
    state: CrownlineSet,
    games: list[GameRecord],
    pair_index: int,
    leg: str,
    first_game_white: Participant,
) -> SetRecord:
    aggregate_a = sum(record.score_a for record in games if record.complete)
    aggregate_b = sum(record.score_b for record in games if record.complete)
    return SetRecord(
        pair_index=pair_index,
        leg=leg,
        first_game_white=first_game_white,
        complete=False,
        winner=None,
        aggregate_a=aggregate_a,
        aggregate_b=aggregate_b,
        capped_game=state.current_game.variant.number,
        games=tuple(games),
    )


def play_benchmark_set(
    engine_a: BenchmarkEngine,
    engine_b: BenchmarkEngine,
    *,
    first_game_white: Participant,
    rules_mode: str = "candidate",
    max_game_plies: int = 300,
    repetition_limit: int = 3,
    pair_index: int = 1,
    leg: str = "A-first",
) -> SetRecord:
    """Play one complete Crownline Set or return a marked harness stop.

    Ply caps and repetition detection are benchmark safety/diagnostic boundaries,
    not Crownline rules. Incomplete sets are excluded from competitive win-rate
    calculations and retained as evidence.
    """

    if max_game_plies < 1:
        raise ValueError("max_game_plies must be at least 1")
    if repetition_limit != 0 and repetition_limit < 2:
        raise ValueError("repetition_limit must be 0 (disabled) or at least 2")
    normalized_mode = normalize_rules_mode(rules_mode)
    state = new_set(first_game_white=first_game_white, rules_mode=normalized_mode)
    engines: dict[Participant, BenchmarkEngine] = {"A": engine_a, "B": engine_b}
    games: list[GameRecord] = []

    while not state.set_over:
        metrics: dict[Participant, ParticipantMetrics] = {
            "A": ParticipantMetrics(),
            "B": ParticipantMetrics(),
        }
        repetition = RepetitionTracker.start(state, limit=repetition_limit)

        while not state.current_game.game_over:
            game = state.current_game
            if game.ply >= max_game_plies:
                games.append(
                    _game_record(
                        state,
                        metrics,
                        complete=False,
                        end_reason="benchmark_ply_cap",
                    )
                )
                return _incomplete_set_record(
                    state=state,
                    games=games,
                    pair_index=pair_index,
                    leg=leg,
                    first_game_white=first_game_white,
                )

            participant = state.participant_for_color(game.turn)
            engine = engines[participant]
            mover_color = game.turn
            before_bank = game.bank(mover_color)
            before_melds = len(game.melds(mover_color))
            before_trigger = game.triggering_player
            sovereign_opportunity = _sovereign_opportunity(game)

            decision = engine.choose(state, participant)
            move = game.move_from_notation(decision.notation)
            mover_piece = game.board[move.path[0]]
            previous_state = state
            next_state = state.apply_move(move, meld_line=decision.meld_line)
            after_game = next_state.current_game
            destination_piece = after_game.board.get(move.path[-1])

            participant_metrics = metrics[participant]
            participant_metrics.record_decision(decision)
            participant_metrics.capture_points += after_game.bank(mover_color) - before_bank
            participant_metrics.crownlines_scored += len(after_game.melds(mover_color)) - before_melds
            participant_metrics.promotions += int(
                bool(destination_piece is not None and not mover_piece.king and destination_piece.king)
            )
            participant_metrics.sovereign_opportunities += int(sovereign_opportunity)
            participant_metrics.sovereign_refusals += int(
                sovereign_opportunity and not move.is_capture
            )
            participant_metrics.quota_triggers += int(
                before_trigger is None and after_game.triggering_player is not None
            )
            participant_metrics.final_response_moves += int(before_trigger is not None)

            state = next_state
            diagnostic = repetition.observe(
                previous_state,
                state,
                participant=participant,
                move=move,
                meld_line=decision.meld_line,
                sovereign_opportunity=sovereign_opportunity,
            )
            if diagnostic is not None:
                games.append(
                    _game_record(
                        state,
                        metrics,
                        complete=False,
                        end_reason="benchmark_repetition_detected",
                        repetition=diagnostic,
                    )
                )
                return _incomplete_set_record(
                    state=state,
                    games=games,
                    pair_index=pair_index,
                    leg=leg,
                    first_game_white=first_game_white,
                )

        games.append(_game_record(state, metrics, complete=True))
        state = state.advance_game()

    aggregate_a, aggregate_b = state.aggregate_scores()
    return SetRecord(
        pair_index=pair_index,
        leg=leg,
        first_game_white=first_game_white,
        complete=True,
        winner=state.winner(),
        aggregate_a=aggregate_a,
        aggregate_b=aggregate_b,
        capped_game=None,
        games=tuple(games),
    )


def _aggregate_participant_metrics(
    records: Tuple[SetRecord, ...], participant: Participant
) -> ParticipantMetrics:
    total = ParticipantMetrics()
    attribute = "metrics_a" if participant == "A" else "metrics_b"
    for set_record in records:
        for game in set_record.games:
            total.absorb(getattr(game, attribute))
    return total


def _metrics_summary(metrics: ParticipantMetrics) -> dict:
    decisions = metrics.decisions
    elapsed_seconds = metrics.elapsed_ms / 1000.0
    return {
        **asdict(metrics),
        "mean_decision_ms": metrics.elapsed_ms / decisions if decisions else 0.0,
        "mean_search_nodes": metrics.search_nodes / decisions if decisions else 0.0,
        "mean_root_actions": metrics.root_actions / decisions if decisions else 0.0,
        "nodes_per_second": metrics.search_nodes / elapsed_seconds if elapsed_seconds > 0 else 0.0,
        "sovereign_refusal_rate": (
            metrics.sovereign_refusals / metrics.sovereign_opportunities
            if metrics.sovereign_opportunities
            else 0.0
        ),
    }


def _build_summary(records: Tuple[SetRecord, ...]) -> dict:
    complete = [record for record in records if record.complete]
    capped = [record for record in records if not record.complete]
    a_wins = sum(record.winner == "A" for record in complete)
    b_wins = sum(record.winner == "B" for record in complete)
    draws = sum(record.winner == "DRAW" for record in complete)
    decisive = a_wins + b_wins
    margins = [record.aggregate_a - record.aggregate_b for record in complete]

    pair_margins = []
    pair_indices = sorted({record.pair_index for record in complete})
    for pair_index in pair_indices:
        pair_records = [record for record in complete if record.pair_index == pair_index]
        if len(pair_records) == 2:
            pair_margins.append(sum(record.aggregate_a - record.aggregate_b for record in pair_records))

    metrics_a = _aggregate_participant_metrics(records, "A")
    metrics_b = _aggregate_participant_metrics(records, "B")

    end_reasons: dict[str, int] = {}
    repetitions = []
    for record in records:
        for game in record.games:
            end_reasons[game.end_reason] = end_reasons.get(game.end_reason, 0) + 1
            if game.repetition is not None:
                repetitions.append(game.repetition)

    return {
        "complete_sets": len(complete),
        "capped_sets": len(capped),
        "repetition_detected_sets": sum(
            any(game.repetition is not None for game in record.games) for record in records
        ),
        "repetition_cycle_lengths": [item.cycle_length for item in repetitions],
        "mean_repetition_cycle_length": (
            mean(item.cycle_length for item in repetitions) if repetitions else 0.0
        ),
        "repetition_escape_actions": [item.escape_actions for item in repetitions],
        "set_wins": {"A": a_wins, "B": b_wins, "draws": draws},
        "decisive_win_rate": {
            "A": a_wins / decisive if decisive else 0.0,
            "B": b_wins / decisive if decisive else 0.0,
        },
        "aggregate_score_totals": {
            "A": sum(record.aggregate_a for record in complete),
            "B": sum(record.aggregate_b for record in complete),
        },
        "mean_set_margin_a_minus_b": mean(margins) if margins else 0.0,
        "paired_margin_a_minus_b": pair_margins,
        "mean_paired_margin_a_minus_b": mean(pair_margins) if pair_margins else 0.0,
        "end_reasons": end_reasons,
        "engine_metrics": {
            "A": _metrics_summary(metrics_a),
            "B": _metrics_summary(metrics_b),
        },
    }


def run_benchmark(
    engine_a: BenchmarkEngine,
    engine_b: BenchmarkEngine,
    *,
    pairs: int = 1,
    rules_mode: str = "candidate",
    max_game_plies: int = 300,
    repetition_limit: int = 3,
) -> BenchmarkReport:
    """Run seat-balanced pairs of complete two-game Crownline Sets."""

    if pairs < 1:
        raise ValueError("pairs must be at least 1")
    if repetition_limit != 0 and repetition_limit < 2:
        raise ValueError("repetition_limit must be 0 (disabled) or at least 2")
    normalized_mode = normalize_rules_mode(rules_mode)
    records: list[SetRecord] = []

    for pair_index in range(1, pairs + 1):
        records.append(
            play_benchmark_set(
                engine_a,
                engine_b,
                first_game_white="A",
                rules_mode=normalized_mode,
                max_game_plies=max_game_plies,
                repetition_limit=repetition_limit,
                pair_index=pair_index,
                leg="A-first",
            )
        )
        records.append(
            play_benchmark_set(
                engine_a,
                engine_b,
                first_game_white="B",
                rules_mode=normalized_mode,
                max_game_plies=max_game_plies,
                repetition_limit=repetition_limit,
                pair_index=pair_index,
                leg="B-first",
            )
        )

    packed = tuple(records)
    return BenchmarkReport(
        schema_version=REPORT_SCHEMA_VERSION,
        rules_mode=normalized_mode,
        pairs=pairs,
        sets_per_pair=2,
        max_game_plies=max_game_plies,
        repetition_limit=repetition_limit,
        deterministic=True,
        engine_a={
            "participant": "A",
            "name": engine_a.name,
            "type": type(engine_a).__name__,
            "depth": getattr(engine_a, "depth", None),
        },
        engine_b={
            "participant": "B",
            "name": engine_b.name,
            "type": type(engine_b).__name__,
            "depth": getattr(engine_b, "depth", None),
        },
        source_fingerprints={
            "baseline_ai_sha256": _source_fingerprint("crownline_ai.py"),
            "rules_engine_sha256": _source_fingerprint(
                "crownline_rules.py",
                "crownline_game.py",
                "crownline_set.py",
            ),
            "benchmark_harness_sha256": _source_fingerprint("crownline_benchmark.py"),
        },
        summary=_build_summary(packed),
        sets=packed,
    )


def report_to_dict(report: BenchmarkReport) -> dict:
    return asdict(report)


def write_report(report: BenchmarkReport, destination: str | Path) -> Path:
    path = Path(destination)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report_to_dict(report), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


def print_summary(report: BenchmarkReport) -> None:
    summary = report.summary
    metrics_a = summary["engine_metrics"]["A"]
    metrics_b = summary["engine_metrics"]["B"]
    wins = summary["set_wins"]
    totals = summary["aggregate_score_totals"]

    print("Crownline AI benchmark")
    print(
        f"Rules: {report.rules_mode} | pairs: {report.pairs} | "
        f"sets: {report.pairs * report.sets_per_pair}"
    )
    print(
        f"A: {report.engine_a['name']} (depth {report.engine_a['depth']}) | "
        f"B: {report.engine_b['name']} (depth {report.engine_b['depth']})"
    )
    print(
        f"Complete sets: {summary['complete_sets']} | capped: {summary['capped_sets']} | "
        f"repetition stops: {summary['repetition_detected_sets']} | "
        f"A wins {wins['A']} | B wins {wins['B']} | draws {wins['draws']}"
    )
    print(
        f"Aggregate score totals: A {totals['A']} — B {totals['B']} | "
        f"mean paired margin A-B {summary['mean_paired_margin_a_minus_b']:.2f}"
    )
    if summary["repetition_detected_sets"]:
        print(
            "Repetition: "
            f"mean cycle {summary['mean_repetition_cycle_length']:.1f} plies | "
            f"cycle lengths {summary['repetition_cycle_lengths']}"
        )
    print(
        f"A search: {metrics_a['decisions']} decisions | "
        f"{metrics_a['mean_decision_ms']:.2f} ms/decision | "
        f"{metrics_a['mean_search_nodes']:.1f} nodes/decision"
    )
    print(
        f"B search: {metrics_b['decisions']} decisions | "
        f"{metrics_b['mean_decision_ms']:.2f} ms/decision | "
        f"{metrics_b['mean_search_nodes']:.1f} nodes/decision"
    )
    print(
        "Events: "
        f"promotions A/B {metrics_a['promotions']}/{metrics_b['promotions']} | "
        f"Crownlines A/B {metrics_a['crownlines_scored']}/{metrics_b['crownlines_scored']} | "
        f"Sovereign refusals A/B {metrics_a['sovereign_refusals']}/{metrics_b['sovereign_refusals']}"
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run reproducible paired-set benchmarks for Crownline computer opponents."
    )
    parser.add_argument("--pairs", type=int, default=1, help="seat-balanced set pairs to run")
    parser.add_argument("--depth-a", type=int, default=2, choices=range(1, 5))
    parser.add_argument("--depth-b", type=int, default=2, choices=range(1, 5))
    parser.add_argument("--name-a", default=None)
    parser.add_argument("--name-b", default=None)
    parser.add_argument(
        "--rules-mode",
        default="candidate",
        choices=("official", "sovereign", "crowned", "candidate"),
    )
    parser.add_argument("--max-game-plies", type=int, default=300)
    parser.add_argument(
        "--repetition-limit",
        type=int,
        default=3,
        help="stop diagnostically on this exact-state occurrence count; 0 disables",
    )
    parser.add_argument("--json", dest="json_path", default=None, help="optional JSON report path")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    engine_a = BaselineEngine(args.name_a or f"baseline-d{args.depth_a}", args.depth_a)
    engine_b = BaselineEngine(args.name_b or f"baseline-d{args.depth_b}", args.depth_b)
    report = run_benchmark(
        engine_a,
        engine_b,
        pairs=args.pairs,
        rules_mode=args.rules_mode,
        max_game_plies=args.max_game_plies,
        repetition_limit=args.repetition_limit,
    )
    print_summary(report)
    if args.json_path:
        path = write_report(report, args.json_path)
        print(f"JSON report: {path}")


if __name__ == "__main__":
    main()
