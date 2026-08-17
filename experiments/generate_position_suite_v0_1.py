from __future__ import annotations

import json
from dataclasses import asdict, dataclass, replace
from typing import Optional, Tuple

from crownline_game import GameState, Line, Move
from crownline_openings import OPENING_SUITE_V0_1, _quantile_index
from crownline_set import CrownlineSet, new_set
from crownline_state_notation import clsn_fingerprint, serialize_clsn


RULES_MODE = "candidate"
SUITE_ID = "v0.1"
SELECTION_METHOD = "legal-action-quantile-applied-independently-to-game1-and-game2"


@dataclass(frozen=True)
class GeneratedStep:
    ply: int
    quantile: float
    legal_actions: int
    selected_index: int
    notation: str
    meld_line: Optional[Line]


@dataclass(frozen=True)
class GeneratedPosition:
    game_number: int
    clsn: str
    fingerprint: str
    trace: Tuple[GeneratedStep, ...]


@dataclass(frozen=True)
class GeneratedScenario:
    scenario_id: str
    description: str
    tags: Tuple[str, ...]
    quantiles: Tuple[float, ...]
    game1: GeneratedPosition
    game2: GeneratedPosition


def _actions(state: CrownlineSet) -> Tuple[tuple[Move, Optional[Line]], ...]:
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


def _initial_set_for_game(game_number: int) -> CrownlineSet:
    state = new_set(first_game_white="A", rules_mode=RULES_MODE)
    if game_number == 1:
        return state
    if game_number == 2:
        return replace(
            state,
            current_game=GameState.initial(2, rules_mode=RULES_MODE),
        )
    raise ValueError("game_number must be 1 or 2")


def _generate_position(game_number: int, quantiles: Tuple[float, ...]) -> GeneratedPosition:
    state = _initial_set_for_game(game_number)
    trace = []
    for quantile in quantiles:
        if state.current_game.game_over:
            raise ValueError(
                f"Game {game_number} ended before the frozen selector prefix completed"
            )
        actions = _actions(state)
        index = _quantile_index(quantile, len(actions))
        move, meld_line = actions[index]
        state = state.apply_move(move, meld_line=meld_line)
        trace.append(
            GeneratedStep(
                ply=state.current_game.ply,
                quantile=quantile,
                legal_actions=len(actions),
                selected_index=index,
                notation=move.notation(),
                meld_line=meld_line,
            )
        )

    return GeneratedPosition(
        game_number=game_number,
        clsn=serialize_clsn(state.current_game),
        fingerprint=clsn_fingerprint(state.current_game),
        trace=tuple(trace),
    )


def generate_suite() -> dict:
    scenarios = []
    for scenario in OPENING_SUITE_V0_1:
        generated = GeneratedScenario(
            scenario_id=scenario.scenario_id,
            description=scenario.description,
            tags=scenario.tags,
            quantiles=scenario.quantiles,
            game1=_generate_position(1, scenario.quantiles),
            game2=_generate_position(2, scenario.quantiles),
        )
        scenarios.append(asdict(generated))

    game1_fingerprints = {item["game1"]["fingerprint"] for item in scenarios}
    game2_fingerprints = {item["game2"]["fingerprint"] for item in scenarios}
    if len(game1_fingerprints) != len(scenarios):
        raise AssertionError("Generated Game 1 suite contains duplicate positions")
    if len(game2_fingerprints) != len(scenarios):
        raise AssertionError("Generated Game 2 suite contains duplicate positions")

    return {
        "suite_id": SUITE_ID,
        "rules_mode": RULES_MODE,
        "selection_method": SELECTION_METHOD,
        "scenario_count": len(scenarios),
        "scenarios": scenarios,
    }


def main() -> None:
    print(json.dumps(generate_suite(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
