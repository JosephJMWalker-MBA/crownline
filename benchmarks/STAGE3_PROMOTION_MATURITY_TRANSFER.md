# Stage 3 Promotion-Maturity Transfer Conclusion

This document records the transfer of the continuous promotion-maturity evaluator from fixed-depth search into the 150 ms iterative structural-TT regime used for Crownline v1.1 opponent research.

The browser opponent remains unchanged.

## 1. Why promotion maturity advanced

The rejected promotion-proximity feature had a semantic cliff: an ordinary piece could be highly valued immediately before promotion and then lose that feature value when it actually became a King. Promotion maturity removed that cliff by defining ordinary-piece progress continuously and treating every realized King as the endpoint `1.0`.

At fixed depth 3, the smallest tested maturity weight, `w10`, changed `0/16` early frozen roots and only `1/12` King hard-case roots while reducing the preserved four-state cycle selections from `3/4` to `2/4`.

The full fixed-depth trajectory test then improved symmetric completion from `10/16` sets to `12/16` and reduced repetition stops from `6` to `4`. In the five complete direct scenario pairs, Baseline A won one, maturity w10 won two, and two drew. Because three pairs were incomplete, that direct result was treated as a favorable signal rather than a strength proof.

Evidence: `benchmarks/stage3_promotion_maturity_diagnostic.json` and `benchmarks/stage3_promotion_maturity_trajectory.json`.

## 2. 150 ms search-regime transfer

A new time-budgeted maturity engine held the Stage-2 architecture fixed:

- iterative deepening;
- 150 ms wall-clock budget;
- maximum depth 4;
- structural exact transposition table;
- unchanged move order and alpha-beta semantics;
- deepest fully completed iteration only.

The only strategic change was replacing Baseline A leaf evaluation with promotion maturity `w10`.

The self-play transfer result was directionally favorable:

| 150 ms self-play engine | Complete sets | Repetition stops | Complete scenario pairs | Mean completed depth |
| --- | ---: | ---: | ---: | ---: |
| Stage-2 control | 2 / 16 | 14 | 1 / 8 | ~3.44 |
| Maturity w10 | 4 / 16 | 12 | 2 / 8 | ~3.34 |

So maturity again improved completion by two sets and reduced repetition by two stops, but the surviving competitive evidence remained sparse.

The direct 150 ms matchup produced only three complete individual sets and **zero complete seat-balanced scenario pairs**. No paired playing-strength claim is therefore justified from this run.

Evidence: `benchmarks/stage3_maturity_transfer_150ms.json`.

## 3. The transfer run exposed a wall-clock evidence issue

An earlier 150 ms Stage-2 control run in the product-composition experiment completed `4/16` sets with 12 repetition stops. The new transfer control completed `2/16` with 14 repetition stops despite using the same conceptual search architecture and approximately the same mean completed depth.

This does not imply hidden randomness in the game. It exposes a different boundary:

> A wall-clock iterative engine is algorithmically deterministic conditional on which search depth fully completes, but the completed depth can depend on runtime timing. A small timing difference can cross a depth boundary, change one move, and send the subsequent deterministic trajectory somewhere else.

Therefore a report field that simply labels every position-suite run `deterministic=true` is too coarse for wall-clock engines. Fixed-depth Crownline search remains deterministic; wall-clock product search is **deadline-sensitive** and should be described separately.

## 4. Root stability audit — early frozen positions

The sixteen early/midgame CLSN roots were each evaluated six times by both the Stage-2 control and maturity w10 under the same 150 ms budget, alternating evaluation order.

Control:

- `0/16` positions showed action variation;
- `0/16` showed completed-depth variation;
- mean completed depth `3.0625`;
- full depth 4 on `6/96` decisions.

Maturity:

- `0/16` positions showed action variation;
- `1/16` showed completed-depth variation;
- mean completed depth `3.0521`;
- full depth 4 on `6/96` decisions.

Control and maturity selected the same action on all `96/96` same-repeat comparisons. That is expected because the earlier fixed-depth diagnostic showed maturity w10 intentionally leaves all sixteen early roots unchanged.

Evidence: `benchmarks/stage3_time_budget_stability_150ms.json`.

## 5. King hard-case stability audit

The more important stability test repeated all twelve artifact-derived King hard cases eight times per engine at 150 ms.

Both engines were highly stable:

- control: `0/12` action-variant positions and `0/12` depth-variant positions;
- maturity: `0/12` action-variant positions and `0/12` depth-variant positions;
- both averaged exactly depth `3.0` over the 96 decisions;
- both reached depth 4 on `8/96` decisions.

The engines differed on exactly one fixture, `standard-start-g1-p200h2h-c4`, and the difference was perfectly repeatable across all eight trials:

```text
Stage-2 control: a5-b4
Maturity w10:    e3-d2
```

That is the same King hard-case policy difference found by the earlier fixed-depth diagnostic. Across all King-suite decisions, the engines agreed on `88/96` actions (`91.67%`), with all eight disagreements concentrated in that one intentional strategic difference.

This is strong evidence that the measured maturity policy effect is **not merely a deadline-jitter artifact**.

Evidence: `benchmarks/stage3_time_budget_king_stability_150ms.json`.

## Decision

1. **Promotion maturity w10 survives the search-regime transfer as a strategic feature candidate.** Its characteristic late-game policy difference remains stable at 150 ms, and it again improved symmetric trajectory completion.
2. **Do not claim standalone 150 ms playing-strength superiority.** The direct transfer matchup contained zero complete scenario pairs.
3. **Do not promote the browser opponent yet.** The product gate remains intentionally stricter than a favorable diagnostic.
4. **Correct benchmark terminology for wall-clock engines.** They are deadline-sensitive even though their search policy is deterministic conditional on completed depth.
5. **Advance to the next isolated composition experiment:** compare the current 150 ms `p200` trajectory-aware opponent against the exact same engine plus promotion maturity w10. This asks whether the strategic feature adds value after repetition handling is already present.

The next experiment therefore changes exactly one strategic dimension on top of the current trajectory control:

```text
control:   iterative TT + p200 exact-history policy
candidate: iterative TT + p200 exact-history policy + promotion maturity w10
```

No Crownline rule change is implied by this work.
