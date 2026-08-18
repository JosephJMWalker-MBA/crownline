from __future__ import annotations

import argparse
import json
from pathlib import Path

from crownline_benchmark import _source_fingerprint
from crownline_position_suite import POSITION_SUITE_ID, POSITION_SUITE_PATH
from experiments.benchmark_maturity_p200_composition_150ms import _composed, _p200, _run_matchup


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = 1


def run(*, budget_ms: float, max_depth: int, repeat_penalty: float, maturity_weight: float, max_game_plies: int, repetition_limit: int) -> dict:
    # Reverse the engine/participant assignment from the first direct composition
    # run. Seat balance inside each scenario still swaps Game-1 White normally.
    matchup = _run_matchup(
        "p200-plus-maturity-vs-p200-control-reversed-role-confirmation",
        _composed("p200-maturity", budget_ms, max_depth, repeat_penalty, maturity_weight),
        _p200("p200-control", budget_ms, max_depth, repeat_penalty),
        max_game_plies=max_game_plies,
        repetition_limit=repetition_limit,
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "experiment": "stage3-p200-plus-promotion-maturity-150ms-reversed-role-confirmation",
        "suite_id": POSITION_SUITE_ID,
        "rules_mode": "candidate",
        "runtime_semantics": "wall-clock-deadline-sensitive",
        "budget_ms": budget_ms,
        "max_depth": max_depth,
        "repeat_penalty": repeat_penalty,
        "maturity_weight": maturity_weight,
        "max_game_plies": max_game_plies,
        "repetition_limit": repetition_limit,
        "hypothesis": (
            "The first direct 150 ms composition run favored p200+maturity w10 in all five complete "
            "scenario pairs (four wins, one draw). Reversing engine assignment to Participants A/B "
            "while retaining each scenario's normal seat-balanced legs should preserve the direction "
            "of the paired result if the advantage is not an assignment or one-run timing artifact."
        ),
        "matchup": matchup,
        "source_fingerprints": {
            "position_suite_sha256": _source_fingerprint(str(POSITION_SUITE_PATH.relative_to(ROOT))),
            "composition_benchmark_sha256": _source_fingerprint("experiments/benchmark_maturity_p200_composition_150ms.py"),
            "confirmation_sha256": _source_fingerprint("experiments/benchmark_maturity_p200_confirmation_150ms.py"),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Confirm p200+maturity at 150 ms with reversed participant assignment.")
    parser.add_argument("--budget-ms", type=float, default=150.0)
    parser.add_argument("--max-depth", type=int, default=4, choices=range(1, 5))
    parser.add_argument("--repeat-penalty", type=float, default=200.0)
    parser.add_argument("--maturity-weight", type=float, default=10.0)
    parser.add_argument("--max-game-plies", type=int, default=300)
    parser.add_argument("--repetition-limit", type=int, default=3)
    parser.add_argument("--json", dest="json_path", default=None)
    args = parser.parse_args()

    report = run(
        budget_ms=args.budget_ms,
        max_depth=args.max_depth,
        repeat_penalty=args.repeat_penalty,
        maturity_weight=args.maturity_weight,
        max_game_plies=args.max_game_plies,
        repetition_limit=args.repetition_limit,
    )
    matchup = report["matchup"]
    s = matchup["summary"]
    print("Crownline p200+maturity reversed-role confirmation")
    print(
        f"complete {s['complete_sets']}/16 | repetitions {s['repetition_stops']} | "
        f"pairs {s['complete_scenario_pairs']}/8 | pair wins {s['scenario_pair_wins']} | "
        f"mean depth A/B {matchup['engine_a']['mean_completed_depth']:.2f}/"
        f"{matchup['engine_b']['mean_completed_depth']:.2f}"
    )

    if args.json_path:
        path = Path(args.json_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"JSON report: {path}")


if __name__ == "__main__":
    main()
