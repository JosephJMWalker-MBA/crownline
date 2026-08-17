from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Tuple

from crownline_state_notation import clsn_fingerprint, parse_clsn, serialize_clsn


ROOT = Path(__file__).resolve().parent
KING_POSITION_SUITE_ID = "king-v0.1"
KING_POSITION_SUITE_RULES_MODE = "candidate"
KING_POSITION_SUITE_PATH = ROOT / "benchmarks" / "king_position_suite_v0_1.json"


@dataclass(frozen=True)
class KingFixtureSource:
    workflow_run: int
    artifact_id: int
    benchmark: str
    scenario_id: str


@dataclass(frozen=True)
class KingPositionFixture:
    fixture_id: str
    description: str
    tags: Tuple[str, ...]
    cycle_length: int
    source: KingFixtureSource
    clsn: str
    fingerprint: str

    def game(self):
        return parse_clsn(self.clsn)

    @property
    def king_count(self) -> int:
        return sum(piece.king for piece in self.game().board.values())


def _source(payload: dict) -> KingFixtureSource:
    return KingFixtureSource(
        workflow_run=int(payload["workflow_run"]),
        artifact_id=int(payload["artifact_id"]),
        benchmark=str(payload["benchmark"]),
        scenario_id=str(payload["scenario_id"]),
    )


def _fixture(payload: dict) -> KingPositionFixture:
    return KingPositionFixture(
        fixture_id=str(payload["fixture_id"]),
        description=str(payload["description"]),
        tags=tuple(str(tag) for tag in payload["tags"]),
        cycle_length=int(payload["cycle_length"]),
        source=_source(payload["source"]),
        clsn=str(payload["clsn"]),
        fingerprint=str(payload["fingerprint"]),
    )


def load_king_position_suite(
    path: str | Path = KING_POSITION_SUITE_PATH,
) -> Tuple[KingPositionFixture, ...]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if payload.get("suite_id") != KING_POSITION_SUITE_ID:
        raise ValueError(f"Expected King position suite {KING_POSITION_SUITE_ID!r}")
    if payload.get("rules_mode") != KING_POSITION_SUITE_RULES_MODE:
        raise ValueError(
            f"King position suite {KING_POSITION_SUITE_ID} must target "
            f"{KING_POSITION_SUITE_RULES_MODE!r} rules"
        )

    fixtures = tuple(_fixture(item) for item in payload["fixtures"])
    if payload.get("fixture_count") != len(fixtures):
        raise ValueError("King position-suite fixture_count does not match fixture list")
    validate_king_position_suite(fixtures)
    return fixtures


def validate_king_position_suite(fixtures: Tuple[KingPositionFixture, ...]) -> None:
    if not fixtures:
        raise ValueError("King position suite must contain at least one fixture")

    fixture_ids: set[str] = set()
    fingerprints: set[str] = set()
    games_seen: set[int] = set()
    cycle_lengths_seen: set[int] = set()

    for fixture in fixtures:
        if not fixture.fixture_id:
            raise ValueError("King position fixture_id must not be empty")
        if fixture.fixture_id in fixture_ids:
            raise ValueError(f"Duplicate King position fixture {fixture.fixture_id!r}")
        fixture_ids.add(fixture.fixture_id)

        if fixture.cycle_length < 2:
            raise ValueError(f"{fixture.fixture_id} has invalid cycle length")
        if fixture.source.workflow_run <= 0 or fixture.source.artifact_id <= 0:
            raise ValueError(f"{fixture.fixture_id} has invalid workflow provenance")
        if not fixture.source.benchmark or not fixture.source.scenario_id:
            raise ValueError(f"{fixture.fixture_id} has incomplete source provenance")

        game = fixture.game()
        games_seen.add(game.variant.number)
        cycle_lengths_seen.add(fixture.cycle_length)
        if game.rules_mode != KING_POSITION_SUITE_RULES_MODE:
            raise ValueError(f"{fixture.fixture_id} has wrong rules mode")
        if game.game_over:
            raise ValueError(f"{fixture.fixture_id} must be non-terminal")
        if serialize_clsn(game) != fixture.clsn:
            raise ValueError(f"{fixture.fixture_id} is not canonical CLSN")

        derived = clsn_fingerprint(game)
        if derived != fixture.fingerprint:
            raise ValueError(f"{fixture.fixture_id} fingerprint does not match CLSN")
        if derived in fingerprints:
            raise ValueError(f"Duplicate canonical King position: {fixture.fixture_id}")
        fingerprints.add(derived)

        kings = [piece for piece in game.board.values() if piece.king]
        if not kings:
            raise ValueError(f"{fixture.fixture_id} must contain at least one King")
        if "cycle" not in fixture.tags:
            raise ValueError(f"{fixture.fixture_id} must be tagged as cycle evidence")
        expected_game_tag = f"game{game.variant.number}"
        if expected_game_tag not in fixture.tags:
            raise ValueError(
                f"{fixture.fixture_id} must include geometry tag {expected_game_tag!r}"
            )
        expected_cycle_tag = f"cycle-{fixture.cycle_length}"
        if expected_cycle_tag not in fixture.tags:
            raise ValueError(
                f"{fixture.fixture_id} must include cycle tag {expected_cycle_tag!r}"
            )

    # These are suite-level coverage guarantees, not game rules. v0.1 exists
    # specifically to guard King-specific evaluator work across both geometries
    # and across the short/medium/long exact-cycle shapes observed in artifacts.
    if games_seen != {1, 2}:
        raise ValueError("King position suite must cover both Game 1 and Game 2")
    if not {4, 8, 20}.issubset(cycle_lengths_seen):
        raise ValueError("King position suite must cover cycle lengths 4, 8, and 20")


def king_position_suite(
    suite_id: str = KING_POSITION_SUITE_ID,
) -> Tuple[KingPositionFixture, ...]:
    if suite_id != KING_POSITION_SUITE_ID:
        raise ValueError(f"Unknown King position suite {suite_id!r}")
    return load_king_position_suite()
