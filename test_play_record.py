from crownline import new_set
from crownline_play_record import (
    PLAY_RECORD_SCHEMA,
    PLAY_RECORD_SCHEMA_VERSION,
    export_play_record,
    new_play_record,
    record_move,
    record_new_set,
)
from crownline_state_notation import parse_clsn, serialize_clsn


def test_play_record_captures_reconstructible_human_decision():
    before_set = new_set(first_game_white="A", rules_mode="candidate")
    record = new_play_record(before_set)
    move = before_set.current_game.legal_moves()[0]
    after_set = before_set.apply_move(move)

    record_move(
        record,
        before_set,
        after_set,
        move,
        meld_line=None,
        controller="human",
    )

    event = record["sets"][0]["games"][0]["moves"][0]
    assert record["schema"] == PLAY_RECORD_SCHEMA
    assert record["schema_version"] == PLAY_RECORD_SCHEMA_VERSION
    assert event["participant"] == "A"
    assert event["color"] == "W"
    assert event["controller"] == "human"
    assert event["notation"] == move.notation()
    assert serialize_clsn(parse_clsn(event["before_clsn"])) == event["before_clsn"]
    assert serialize_clsn(parse_clsn(event["after_clsn"])) == event["after_clsn"]
    assert event["before_clsn"] != event["after_clsn"]
    assert event["ai"] is None


def test_play_record_preserves_computer_search_evidence():
    before_set = new_set(first_game_white="A", rules_mode="candidate")
    first = before_set.current_game.legal_moves()[0]
    before_set = before_set.apply_move(first)
    record = new_play_record(before_set)
    move = before_set.current_game.legal_moves()[0]
    after_set = before_set.apply_move(move)
    evidence = {
        "profile": "research",
        "budget_ms": 150.0,
        "completed_depth": 3,
        "search_nodes": 421,
    }

    record_move(
        record,
        before_set,
        after_set,
        move,
        meld_line=None,
        controller="computer",
        ai_evidence=evidence,
    )

    event = record["sets"][0]["games"][0]["moves"][0]
    assert event["participant"] == "B"
    assert event["controller"] == "computer"
    assert event["ai"] == evidence
    assert event["ai"] is not evidence


def test_export_summary_counts_human_and_computer_moves():
    state = new_set(first_game_white="A", rules_mode="candidate")
    record = new_play_record(state)

    human_move = state.current_game.legal_moves()[0]
    after_human = state.apply_move(human_move)
    record_move(
        record,
        state,
        after_human,
        human_move,
        meld_line=None,
        controller="human",
    )

    computer_move = after_human.current_game.legal_moves()[0]
    after_computer = after_human.apply_move(computer_move)
    record_move(
        record,
        after_human,
        after_computer,
        computer_move,
        meld_line=None,
        controller="computer",
        ai_evidence={"profile": "baseline", "depth": 2},
    )

    payload = export_play_record(record, after_computer)
    assert payload["summary"]["moves_recorded"] == 2
    assert payload["summary"]["human_moves_recorded"] == 1
    assert payload["summary"]["computer_moves_recorded"] == 1
    assert payload["summary"]["games_recorded"] == 1
    assert payload["summary"]["current_rules_mode"] == "candidate"


def test_reset_starts_new_set_without_discarding_previous_moves():
    state = new_set(first_game_white="A", rules_mode="candidate")
    record = new_play_record(state)
    move = state.current_game.legal_moves()[0]
    after = state.apply_move(move)
    record_move(
        record,
        state,
        after,
        move,
        meld_line=None,
        controller="human",
    )

    reset_state = new_set(first_game_white="A", rules_mode="candidate")
    record_new_set(record, reset_state, opened_reason="reset")
    payload = export_play_record(record, reset_state)

    assert payload["summary"]["sets_recorded"] == 2
    assert payload["summary"]["games_recorded"] == 2
    assert payload["summary"]["moves_recorded"] == 1
    assert payload["sets"][0]["closed_reason"] == "reset"
    assert payload["sets"][1]["opened_reason"] == "reset"
