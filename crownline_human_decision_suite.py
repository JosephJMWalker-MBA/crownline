from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional, Tuple

from crownline_rules import Line, Participant, Player
from crownline_set import CrownlineSet
from crownline_state_notation import clsn_fingerprint, parse_clsn, serialize_clsn


ROOT = Path(__file__).resolve().parent
HUMAN_SUITE_ID = "human-v0.1"
HUMAN_SUITE_RULES_MODE = "candidate"
HUMAN_SUITE_PATH = ROOT / "benchmarks" / "human_decision_suite_v0_1.json"


@dataclass(frozen=True)
class HumanDecisionAction:
    notation: str
    meld_line: Optional[Line]


@dataclass(frozen=True)
class HumanDecisionFixture:
    fixture_id: str
    bucket: str
    source: str
    set_sequence: int
    game_number: int
    move_index: int
    first_game_white: Participant
    participant: Participant
    color: Player
    controller: str
    clsn: str
    fingerprint: str
    observed_action: HumanDecisionAction
    annotation: dict[str, Any]

    def game(self):
        return parse_clsn(self.clsn)

    def state(self) -> CrownlineSet:
        return CrownlineSet(
            first_game_white=self.first_game_white,
            current_game=self.game(),
            rules_mode=HUMAN_SUITE_RULES_MODE,
        )


def _action(payload: dict[str, Any]) -> HumanDecisionAction:
    meld_line = payload.get("meld_line")
    return HumanDecisionAction(
        notation=str(payload["notation"]),
        meld_line=tuple(meld_line) if meld_line else None,
    )


def _fixture(payload: dict[str, Any]) -> HumanDecisionFixture:
    return HumanDecisionFixture(
        fixture_id=str(payload["fixture_id"]),
        bucket=str(payload["bucket"]),
        source=str(payload["source"]),
        set_sequence=int(payload["set_sequence"]),
        game_number=int(payload["game_number"]),
        move_index=int(payload["move_index"]),
        first_game_white=str(payload["first_game_white"]),  # type: ignore[arg-type]
        participant=str(payload["participant"]),  # type: ignore[arg-type]
        color=str(payload["color"]),  # type: ignore[arg-type]
        controller=str(payload["controller"]),
        clsn=str(payload["clsn"]),
        fingerprint=str(payload["fingerprint"]),
        observed_action=_action(payload["observed_action"]),
        annotation=dict(payload.get("annotation") or {}),
    )


def load_human_decision_suite(
    manifest_path: str | Path = HUMAN_SUITE_PATH,
) -> Tuple[HumanDecisionFixture, ...]:
    path = Path(manifest_path)
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if manifest.get("schema") != "crownline.human-decision-suite":
        raise ValueError("Unexpected human decision suite schema")
    if manifest.get("schema_version") != 1:
        raise ValueError("Unsupported human decision suite schema version")
    if manifest.get("suite_id") != HUMAN_SUITE_ID:
        raise ValueError(f"Expected suite {HUMAN_SUITE_ID!r}")
    if manifest.get("rules_mode") != HUMAN_SUITE_RULES_MODE:
        raise ValueError("Human decision suite must target the v1.1 candidate rules")

    fixtures = []
    for relative in manifest["fixture_files"]:
        fixture_path = path.parent / str(relative)
        payload = json.loads(fixture_path.read_text(encoding="utf-8"))
        if payload.get("schema") != "crownline.human-decision-fixtures":
            raise ValueError(f"Unexpected fixture schema in {fixture_path.name}")
        if payload.get("schema_version") != 1:
            raise ValueError(f"Unsupported fixture schema in {fixture_path.name}")
        bucket = str(payload["bucket"])
        items = tuple(_fixture(item) for item in payload["fixtures"])
        if payload.get("fixture_count") != len(items):
            raise ValueError(f"Fixture count mismatch in {fixture_path.name}")
        if any(item.bucket != bucket for item in items):
            raise ValueError(f"Bucket mismatch in {fixture_path.name}")
        fixtures.extend(items)

    packed = tuple(fixtures)
    if manifest.get("fixture_count") != len(packed):
        raise ValueError("Human decision suite fixture_count does not match fixture files")

    expected_bucket_counts = {
        str(key): int(value)
        for key, value in (manifest.get("bucket_counts") or {}).items()
    }
    actual_bucket_counts: dict[str, int] = {}
    for fixture in packed:
        actual_bucket_counts[fixture.bucket] = actual_bucket_counts.get(fixture.bucket, 0) + 1
    if actual_bucket_counts != expected_bucket_counts:
        raise ValueError("Human decision suite bucket counts do not match fixture files")

    validate_human_decision_suite(packed)
    return packed


def validate_human_decision_suite(fixtures: Tuple[HumanDecisionFixture, ...]) -> None:
    if not fixtures:
        raise ValueError("Human decision suite must contain fixtures")

    ids: set[str] = set()
    fingerprints: set[str] = set()
    for fixture in fixtures:
        if fixture.fixture_id in ids:
            raise ValueError(f"Duplicate fixture id {fixture.fixture_id!r}")
        ids.add(fixture.fixture_id)
        if fixture.fingerprint in fingerprints:
            raise ValueError(f"Duplicate fixture position {fixture.fixture_id!r}")
        fingerprints.add(fixture.fingerprint)

        game = fixture.game()
        if game.variant.number != fixture.game_number:
            raise ValueError(f"{fixture.fixture_id}: game-number mismatch")
        if game.rules_mode != HUMAN_SUITE_RULES_MODE:
            raise ValueError(f"{fixture.fixture_id}: wrong rules mode")
        if game.game_over:
            raise ValueError(f"{fixture.fixture_id}: fixture must be non-terminal")
        if game.turn != fixture.color:
            raise ValueError(f"{fixture.fixture_id}: side-to-move mismatch")
        if serialize_clsn(game) != fixture.clsn:
            raise ValueError(f"{fixture.fixture_id}: CLSN is not canonical")
        if clsn_fingerprint(game) != fixture.fingerprint:
            raise ValueError(f"{fixture.fixture_id}: fingerprint mismatch")

        state = fixture.state()
        if state.participant_for_color(game.turn) != fixture.participant:
            raise ValueError(f"{fixture.fixture_id}: participant mapping mismatch")
        move = game.move_from_notation(fixture.observed_action.notation)
        options = game.meld_options_after(move)
        option_lines = {meld.line for meld in options}
        if fixture.observed_action.meld_line is None:
            if len(options) > 1:
                raise ValueError(
                    f"{fixture.fixture_id}: observed move requires a Crownline choice"
                )
        elif fixture.observed_action.meld_line not in option_lines:
            raise ValueError(f"{fixture.fixture_id}: observed Crownline choice is not legal")

        if fixture.bucket == "human-tactical-error":
            after = state.apply_move(move, meld_line=fixture.observed_action.meld_line)
            reply_text = str(fixture.annotation["observed_reply"])
            reply = after.current_game.move_from_notation(reply_text)
            legs = len(reply.captured)
            points = sum(
                after.current_game.board[square].capture_value()
                for square in reply.captured
            )
            if legs != int(fixture.annotation["observed_reply_capture_legs"]):
                raise ValueError(f"{fixture.fixture_id}: reply capture-leg annotation mismatch")
            if points != int(fixture.annotation["observed_reply_capture_points"]):
                raise ValueError(f"{fixture.fixture_id}: reply capture-point annotation mismatch")


def human_decision_suite(
    suite_id: str = HUMAN_SUITE_ID,
) -> Tuple[HumanDecisionFixture, ...]:
    if suite_id != HUMAN_SUITE_ID:
        raise ValueError(f"Unknown human decision suite {suite_id!r}")
    return load_human_decision_suite()
