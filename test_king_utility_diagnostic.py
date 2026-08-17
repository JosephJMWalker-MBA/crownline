from experiments.diagnose_king_utility import (
    _early_feature_ranges,
    _king_hard_case_feature_ranges,
)


def test_early_control_has_no_kings_but_hard_case_suite_does():
    early = _early_feature_ranges()
    hard = _king_hard_case_feature_ranges()

    assert early["positions"] == 16
    assert early["positions_containing_kings"] == 0
    assert hard["positions"] == 12
    assert hard["king_count_range"][0] >= 2
    assert hard["king_count_range"][1] >= 6


def test_king_hard_case_suite_activates_every_king_feature_family():
    hard = _king_hard_case_feature_ranges()
    ranges = hard["ranges"]

    king_keys = (
        "king_count",
        "king_board_value",
        "king_step_options",
        "king_backward_steps",
        "king_capture_paths",
        "king_unretired_line_incidence",
        "king_safety",
        "king_threat_path_safety",
    )
    for key in king_keys:
        assert ranges[key]["distinct"] > 1, key
        assert ranges[key]["nonzero_observations"] > 0, key

    assert hard["game_numbers"] == [1, 2]
    assert hard["cycle_lengths"] == [4, 8, 20]
