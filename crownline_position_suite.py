from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Tuple

from crownline_state_notation import clsn_fingerprint, parse_clsn, serialize_clsn


ROOT = Path(__file__).resolve().parent
POSITION_SUITE_ID = "v0.1"
POSITION_SUITE_RULES_MODE = "candidate"
POSITION_SUITE_PATH = ROOT / "benchmarks" / "position_suite_v0_1.json"


@dataclass(frozen=True)
class PositionFixture:
    clsn: str
    fingerprint: str

    def game(self):
        return parse_clsn(self.clsn)


@dataclass(frozen=True)
class PositionScenario:
    scenario_id: str
    description: str
    tags: Tuple[str, ...]
    provenance_quantiles: Tuple[float, ...]
    game1: PositionFixture
    game2: PositionFixture


def _fixture(payload: dict) -> PositionFixture:
    return PositionFixture(
        clsn=str(payload["clsn"]),
        fingerprint=str(payload["fingerprint"]),
    )


def _scenario(payload: dict) -> PositionScenario:
    return PositionScenario(
        scenario_id=str(payload["scenario_id"]),
        description=str(payload["description"]),
        tags=tuple(str(tag) for tag in payload["tags"]),
        provenance_quantiles=tuple(float(value) for value in payload["provenance_quantiles"]),
        game1=_fixture(payload["game1"]),
        game2=_fixture(payload["game2"]),
    )


def load_position_suite(path: str | Path = POSITION_SUITE_PATH) -> Tuple[PositionScenario, ...]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if payload.get("suite_id") != POSITION_SUITE_ID:
        raise ValueError(f"Expected position suite {POSITION_SUITE_ID!r}")
    if payload.get("rules_mode") != POSITION_SUITE_RULES_MODE:
        raise ValueError(
            f"Position suite {POSITION_SUITE_ID} must target {POSITION_SUITE_RULES_MODE!r} rules"
        )
    scenarios = tuple(_scenario(item) for item in payload["scenarios"])
    if payload.get("scenario_count") != len(scenarios):
        raise ValueError("Position-suite scenario_count does not match the fixture list")
    validate_position_suite(scenarios)
    return scenarios


def validate_position_suite(scenarios: Tuple[PositionScenario, ...]) -> None:
    if not scenarios:
        raise ValueError("Position suite must contain at least one scenario")

    scenario_ids: set[str] = set()
    fingerprints: set[str] = set()
    for scenario in scenarios:
        if scenario.scenario_id in scenario_ids:
            raise ValueError(f"Duplicate position scenario {scenario.scenario_id!r}")
        scenario_ids.add(scenario.scenario_id)

        for game_number, fixture in ((1, scenario.game1), (2, scenario.game2)):
            game = fixture.game()
            if game.variant.number != game_number:
                raise ValueError(
                    f"{scenario.scenario_id} Game {game_number} fixture has wrong geometry"
                )
            if game.rules_mode != POSITION_SUITE_RULES_MODE:
                raise ValueError(
                    f"{scenario.scenario_id} Game {game_number} fixture has wrong rules mode"
                )
            if game.game_over:
                raise ValueError(
                    f"{scenario.scenario_id} Game {game_number} fixture must be non-terminal"
                )
            if serialize_clsn(game) != fixture.clsn:
                raise ValueError(
                    f"{scenario.scenario_id} Game {game_number} fixture is not canonical CLSN"
                )
            derived = clsn_fingerprint(game)
            if derived != fixture.fingerprint:
                raise ValueError(
                    f"{scenario.scenario_id} Game {game_number} fingerprint does not match CLSN"
                )
            if derived in fingerprints:
                raise ValueError(
                    f"Duplicate canonical position in suite: {scenario.scenario_id} Game {game_number}"
                )
            fingerprints.add(derived)


def position_suite(suite_id: str = POSITION_SUITE_ID) -> Tuple[PositionScenario, ...]:
    if suite_id != POSITION_SUITE_ID:
        raise ValueError(f"Unknown position suite {suite_id!r}")
    return load_position_suite()
