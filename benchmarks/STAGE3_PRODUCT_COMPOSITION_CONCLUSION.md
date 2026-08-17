# Stage 3 Product Composition Conclusion

This document closes the first attempt to turn the independently measured Stage-2 search substrate and Stage-3 trajectory policy into one browser-scale opponent candidate under Crownline v1.1 (`candidate`).

The browser opponent remains unchanged.

## Candidate architecture

The composed experimental opponent keeps Crownline's rules and Baseline A's static evaluator unchanged. It combines:

1. Stage 2 iterative deepening under a wall-clock budget;
2. the CLSN-equivalent structural exact transposition table;
3. a root-level exact-history penalty when the same participant considers recreating an afterstate it has previously produced in the current game.

`crownline_product_candidate.py` exposes the composed engine and a Stage-2-only time-budgeted control. A zero history penalty is regression-tested to preserve the Stage-2 structural-TT policy when both searches complete the same depth.

The quota/final-response horizon extension is deliberately excluded because its independent composition experiment did not earn inclusion.

## Why the fixed-depth p50 result did not transfer directly

At fixed depth 3, a 50-point repeat penalty was the smallest tested intervention that reduced repetition stops from 6 to 2 without a measured paired strength loss. It was therefore the correct first composition candidate.

The product architecture changes the search regime, however. At a 150 ms budget the iterative structural-TT engine usually completes depth 3 and sometimes depth 4. The resulting minimax gaps and future trajectory are not identical to the fixed-depth-3 experiment. The history penalty therefore had to be revalidated rather than copied mechanically.

## 150 ms p50 composition

The first product-scale benchmark compared:

- Stage-2 structural-TT time control vs itself;
- the same search substrate plus p50 history policy vs itself;
- Stage-2 control vs the p50 product candidate.

All engines used a 150 ms budget and maximum depth 4 over the frozen eight-scenario / sixteen-set structure.

| Self-play engine | Complete sets | Repetition stops | Complete scenario pairs | Mean completed depth |
| --- | ---: | ---: | ---: | ---: |
| Stage-2 control | 4 / 16 | 12 | 2 / 8 | ~3.43 |
| Product p50 | 7 / 16 | 9 | 3 / 8 | ~3.29 |

The p50 policy therefore improved completion, but not nearly enough to qualify as a product solution. More importantly, the remaining repetition diagnostics changed shape: the p50 run contained two **20-ply** exact-state cycles in addition to the familiar four-ply loops. This is evidence that a policy can suppress one local trajectory while exposing a longer one.

In the direct mixed matchup, only three scenario pairs completed. The Stage-2 control won one paired aggregate and two drew; the p50 candidate won none. That evidence is too incomplete to support a strength claim.

Evidence: workflow `32054333022`, artifact `9296124685`, artifact SHA-256 `125c810fc317f581a7372decfbcd45b68c01dd220f6a6535c163cd73f76595e3`. All 111 tests passed before the benchmark.

## Retuning inside the actual 150 ms search regime

Because p50 was calibrated under the wrong search regime for product use, the next measurement changed only the repeat penalty while keeping the 150 ms structural-TT architecture fixed.

A p200 symmetric self-play run produced:

```text
complete sets:          11 / 16
repetition stops:        5
complete scenario pairs: 5 / 8
mean completed depth:   ~3.26 / ~3.26
cycle lengths:           4, 4, 4, 4, 4
```

There were no ply-cap stops. Every incomplete set stopped on exact-state repetition. The 20-ply cycles seen at p50 disappeared in this run.

The result is materially better than both the Stage-2-only control (`4/16`, 12 repetitions) and the p50 composition (`7/16`, 9 repetitions), although it still falls short of making repetition a solved product problem.

Evidence: workflow `32055444693`, artifact `9296362998`, artifact SHA-256 `ee94b811538f821b2b5fd27addaa72e02635375d15a64834de09cb7a3bee9f9a`. All 111 tests passed before the benchmark.

## p200 direct comparison with Stage-2 control

The p200 candidate then played the Stage-2 time-budgeted control directly with the same seat-balanced frozen-suite structure.

Results:

```text
complete sets:           11 / 16
repetition stops:         5
complete scenario pairs:  4 / 8
paired result:             control 1 / p200 0 / draws 3
paired margins control-p200: +41, 0, 0, 0
```

The individual completed sets tell a different-looking story: p200 won 7 complete sets to the control's 4, and completed-set aggregate score was 932 for p200 versus 801 for the control. Those totals cannot be treated as stronger evidence than the paired result because five sets stopped on repetition and only four full scenario pairs survived the completion filter. The seat-balanced paired evidence is therefore deliberately given priority.

The p200 candidate also completed slightly less search depth on average (`3.41` versus `3.44` for the control), consistent with the extra root-history fingerprint work carrying a small computational cost.

Evidence: workflow `32056116528`, artifact `9296560712`, artifact SHA-256 `79cc95818f17091d4671217e7ed0a846dbb6abbce07fabdb691ec79d3088efcc`. All 111 tests passed before the benchmark.

## Decision

The product-composition evidence supports a narrower conclusion than the fixed-depth experiment did:

1. **Exact trajectory memory is genuinely useful.** In the actual 150 ms architecture it reduced repetition substantially, and increasing the penalty from 50 to 200 improved completion again.
2. **The penalty is search-regime dependent.** A value calibrated at fixed depth 3 should not be assumed optimal under iterative deepening where some decisions complete depth 4.
3. **p200 is the leading anti-cycle control for the current 150 ms architecture, not a promoted product opponent.** It reduced repetition to 5/16 but did not establish paired playing-strength superiority or non-inferiority strongly enough for browser replacement.
4. **Do not keep increasing the penalty blindly.** Earlier fixed-depth p500 evidence produced two ply caps, showing that stronger repetition aversion can create a different stalling pathology.
5. **Do not change Crownline's game rules to solve this.** All measured cases remain AI-policy/search behavior.
6. **Do not change the browser opponent yet.** The current research candidate has improved materially, but it has not passed the product gate.

## Next research boundary

The trajectory layer has now been pushed far enough to expose diminishing returns. The remaining loops repeatedly survive even when returning to an exact afterstate costs 200 evaluator points. That is evidence that the underlying position valuation can still make reversible King motion look strategically compelling by a large margin.

The next Stage-3 experiment should therefore return to **strategic evaluation**, while keeping trajectory handling independently switchable.

The strongest next target is **promotion / King utility**:

> Baseline A values a King mostly through whatever board-square score and mobility it happens to have at the current state. Crownline v1.1 gives Kings additional game-specific strategic authority: they enable Crownline scoring, double capture value when lost, move backward, and can release a Sovereign turn from mandatory capture. A useful evaluator should measure those consequences without simply assigning a constant "King bonus."

The experiment should first decompose measurable King utility into transparent components and test them on the frozen root suite and preserved cycle states before any full-trajectory run. The p200 history policy should remain a separately switchable trajectory control, not be baked into the strategic feature itself.
