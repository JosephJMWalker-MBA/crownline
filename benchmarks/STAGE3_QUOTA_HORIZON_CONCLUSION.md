# Stage 3 Quota-Horizon Conclusion

This experiment tested one narrow Crownline-specific search question under v1.1 (`candidate`):

> **Should search resolve the mandatory final-response turn when the ordinary depth cutoff lands immediately after the capture quota is crossed?**

The browser opponent remains unchanged.

## Why this boundary exists

Crossing the capture quota does not immediately end a Crownline game. The opponent receives exactly one final response turn and the game then scores.

Baseline A can therefore reach a depth cutoff in the unique state between those events:

```text
quota crossed -> triggering_player set -> opponent final response still pending
```

At an ordinary cutoff Baseline A evaluates that state as nonterminal even though exactly one game turn remains. The experiment introduced no new score term. It simply resolved that forced final response before evaluating such a leaf.

The behavior was regression-tested against the Game-2 King-recapture position already preserved from live play. With the extension enabled, the depth-zero value equals the true terminal evaluation after the required response. With the extension disabled, frozen-suite policy remains Baseline-equivalent.

## Isolated depth-3 trajectory result

The first full frozen-suite run compared Baseline self-play, quota-horizon self-play, and Baseline vs quota-horizon at fixed depth 3.

The extension was active frequently—1,624 extended leaves per participant in symmetric quota-horizon self-play—yet it changed **0/16 frozen root actions**.

| Matchup | Complete sets | Repetition stops | Complete scenario pairs |
| --- | ---: | ---: | ---: |
| Baseline self-play | 10 / 16 | 6 | 5 / 8 |
| Quota-horizon self-play | 10 / 16 | 6 | 5 / 8 |
| Baseline vs quota-horizon | 12 / 16 | 4 | 6 / 8 |

The symmetric candidate therefore produced no completion or repetition improvement by itself. In the six complete mixed scenario pairs, Baseline won three paired aggregates, quota-horizon won one, and two drew.

Evidence: workflow `32053154159`, artifact `9295485020`, SHA-256 `6c5cd4121e58958b7e4f331e9cc1d460b9015f7c217aae56ab90d6fd109a355c`. All 104 tests passed before the benchmark.

## Composition with the measured repeat policy

Because exact four-ply repetition was already known to obscure full-trajectory evidence, the extension was then tested on top of the independently measured 50-point actual-history repeat policy.

The control was `RepeatAwareEngine(penalty=50)`. The candidate kept that same history policy and added only the final-response horizon extension.

Symmetric self-play was nearly identical in completion behavior:

| Engine | Complete sets | Repetition stops | Complete scenario pairs |
| --- | ---: | ---: | ---: |
| Repeat-aware p50 | 14 / 16 | 2 | 7 / 8 |
| Repeat-aware p50 + quota horizon | 14 / 16 | 2 | 7 / 8 |

The quota extension fired 2,062 times per participant in the composed self-play, so the null completion result is not because the code path was dormant.

The direct mixed comparison was more informative. Fifteen of sixteen sets completed and seven scenario pairs were complete. The plain repeat-aware engine won **4** paired aggregates, the composed engine won **1**, and **2** drew. The paired margins from the repeat-aware participant's perspective were:

```text
0, +24, -50, 0, +1, +42, +5
```

The mean paired margin was +3.14 for the plain repeat-aware engine. Completed-set aggregate scores were 994 for repeat-aware versus 907 for repeat-plus-quota. Those totals are descriptive rather than independent strength proof, but they point in the same direction as the paired result.

Evidence: workflow `32053708057`, artifact `9295694839`, SHA-256 `c4dfb85693fc0d82c4bf5b44d8d78d5b5473f96806af08d5cf6199bdec33ac26`. All 107 tests passed before the benchmark.

## Decision

The experiment established a useful distinction between **semantic precision** and **playing-strength value**.

The final-response extension is semantically clean: when search lands on a quota-triggered leaf, resolving the one rule-forced response gives a more faithful value for that local tactical horizon. The targeted regression demonstrates that clearly.

But the measured trajectory evidence does not justify putting the extension into the product opponent. It did not improve symmetric completion or repetition, and when composed with the leading repeat-aware policy it lost four of seven complete paired scenario aggregates to the simpler history-only engine.

Therefore:

1. **Retain the quota-horizon implementation and tests as experimental evidence.**
2. **Do not promote it into the browser or the next product opponent candidate.**
3. **Keep the 50-point exact-history repeat policy as the Stage-3 control that earned composition with Stage-2 search engineering.**
4. **The next coherent opponent candidate should combine Stage-2 iterative deepening + structural exact TT with the p50 repeat policy, without quota extension.**

This keeps the architecture evidence-driven: exact cycle history is promoted as a policy candidate because it materially improved completion without measured paired loss; quota-horizon resolution remains available for future tactical study but has not earned product inclusion.
