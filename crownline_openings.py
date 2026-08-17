from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

from crownline_game import Line, Move
from crownline_rules import Participant
from crownline_set import CrownlineSet, new_set


OPENING_SUITE_ID = "v0.1"
OPENING_RULES_MODE = "candidate"
OPENING_SELECTION_METHOD = "legal-action-quantile"


@dataclass(frozen=True)
class OpeningStep:
    ply: int
    quantile: float
    legal_actions: int
    selected_index: int
    notation: str
    meld_line: Optional[Line]


@dataclass(frozen=True)
class OpeningScenario:
    scenario_id: str
    description: str
    tags: Tuple[str, ...]
    quantiles: Tuple[float, ...]
    rules_mode: str = OPENING_RULES_MODE

    @property
    def opening_plies(self) -> int:
        return len(self.quantiles)


def _scenario_actions(state: CrownlineSet) -> Tuple[tuple[Move, Optional[Line]], ...]:
    """Return a stable ordering of legal move + Crownline-choice actions."""

    actions: list[tuple[Move, Optional[Line]]] = []
    game = state.current_game
    for move in game.legal_moves():
        melds = game.meld_options_after(move)
        if len(melds) > 1:
            actions.extend((move, meld.line) for meld in melds)
        else:
            actions.append((move, melds[0].line if melds else None))
    return tuple(
        sorted(
            actions,
            key=lambda item: (
                item[0].notation(),
                "" if item[1] is None else "-".join(item[1]),
            ),
        )
    )


def _quantile_index(quantile: float, count: int) -> int:
    if not 0.0 <= quantile <= 1.0:
        raise ValueError("opening quantiles must be between 0 and 1")
    if count < 1:
        raise ValueError("cannot select an opening action from an empty legal action set")
    # Round half up rather than using Python's banker's rounding so the mapping is
    # explicit and language-independent for the fixed suite.
    return min(count - 1, int(quantile * (count - 1) + 0.5))


def instantiate_opening(
    scenario: OpeningScenario,
    *,
    first_game_white: Participant,
) -> tuple[CrownlineSet, Tuple[OpeningStep, ...]]:
    """Replay a frozen, AI-independent v1.1 opening prefix from the standard start.

    The selectors depend only on the authoritative legal-action ordering. No bot
    evaluation, randomness, score heuristic, or search result chooses the prefix.
    The returned state remains an ordinary CrownlineSet and therefore continues
    through the rest of Game 1 and the standard complementary Game 2 normally.
    """

    if scenario.rules_mode != OPENING_RULES_MODE:
        raise ValueError(
            f"Opening suite {OPENING_SUITE_ID} targets {OPENING_RULES_MODE!r} rules only"
        )
    state = new_set(first_game_white=first_game_white, rules_mode=scenario.rules_mode)
    trace: list[OpeningStep] = []

    for quantile in scenario.quantiles:
        if state.current_game.game_over:
            raise ValueError(
                f"Scenario {scenario.scenario_id} ended before its opening prefix completed"
            )
        actions = _scenario_actions(state)
        index = _quantile_index(quantile, len(actions))
        move, meld_line = actions[index]
        state = state.apply_move(move, meld_line=meld_line)
        trace.append(
            OpeningStep(
                ply=state.current_game.ply,
                quantile=quantile,
                legal_actions=len(actions),
                selected_index=index,
                notation=move.notation(),
                meld_line=meld_line,
            )
        )

    return state, tuple(trace)


# v0.1 deliberately samples the legal-action ordering rather than asking the
# current bot to generate openings. This keeps the scenarios independent of the
# engine under test. The empty control preserves the untouched standard start;
# the seven eight-ply prefixes spread across low/middle/high action quantiles.
OPENING_SUITE_V0_1: Tuple[OpeningScenario, ...] = (
    OpeningScenario(
        "standard-start",
        "Untouched Game 1 starting position; control condition.",
        ("control", "early"),
        (),
    ),
    OpeningScenario(
        "low-lattice",
        "Eight-ply prefix biased toward lower-ranked legal actions.",
        ("early", "low-quantile"),
        (0.00, 0.25, 0.00, 0.25, 0.00, 0.25, 0.00, 0.25),
    ),
    OpeningScenario(
        "high-lattice",
        "Eight-ply prefix biased toward higher-ranked legal actions.",
        ("early", "high-quantile"),
        (1.00, 0.75, 1.00, 0.75, 1.00, 0.75, 1.00, 0.75),
    ),
    OpeningScenario(
        "median-line",
        "Eight-ply prefix repeatedly selecting the median legal action.",
        ("early", "median"),
        (0.50, 0.50, 0.50, 0.50, 0.50, 0.50, 0.50, 0.50),
    ),
    OpeningScenario(
        "quarter-cross-a",
        "Alternating lower/upper quartiles with a two-step crossing rhythm.",
        ("early", "mixed-quantile"),
        (0.25, 0.75, 0.75, 0.25, 0.25, 0.75, 0.75, 0.25),
    ),
    OpeningScenario(
        "quarter-cross-b",
        "Seat-neutral complement of quarter-cross-a's selector rhythm.",
        ("early", "mixed-quantile"),
        (0.75, 0.25, 0.25, 0.75, 0.75, 0.25, 0.25, 0.75),
    ),
    OpeningScenario(
        "full-spread",
        "Eight-ply prefix spanning extremes, median, and both quartiles.",
        ("early", "mixed-quantile"),
        (0.00, 1.00, 0.50, 0.25, 0.75, 1.00, 0.00, 0.50),
    ),
    OpeningScenario(
        "weave",
        "Eight-ply mixed selector intended to create a distinct development path.",
        ("early", "mixed-quantile"),
        (0.50, 0.00, 1.00, 0.50, 0.75, 0.25, 0.50, 1.00),
    ),
)


def opening_suite(suite_id: str = OPENING_SUITE_ID) -> Tuple[OpeningScenario, ...]:
    if suite_id != OPENING_SUITE_ID:
        raise ValueError(f"Unknown opening suite {suite_id!r}")
    return OPENING_SUITE_V0_1
