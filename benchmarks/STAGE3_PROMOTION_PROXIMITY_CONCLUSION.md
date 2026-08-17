# Stage 3 Promotion-Proximity Conclusion

This experiment tested a deliberately narrow strategic hypothesis under Crownline v1.1 (`candidate`):

> **Does Baseline A undervalue ordinary pieces that are approaching promotion because final board-square score can pull in a different direction from future King authority?**

The browser opponent remains unchanged.

## Guardrail improvement first

Before assigning any King-specific evaluator weight, Stage 3 exposed a benchmark-quality problem: the original frozen 16-position CLSN suite contains **no Kings**. It remains a useful early/midgame policy guardrail, but it cannot detect late-game King-specific policy disruption.

A separate artifact-derived `king-v0.1` hard-case suite was therefore frozen from twelve exact repeated CLSN states reached by measured 150 ms p50/p200 trajectories. It covers both game geometries, two through six Kings, banked ordinary and Royal Crownlines, and exact cycle lengths of 4, 8, and 20 plies. This suite is a root/evaluator guardrail, not a paired competitive benchmark.

The first feature diagnostic confirmed that every measured King-feature family varies on the new suite while every King-feature margin is identically zero on the original suite.

## First promotion formulation: unrealized proximity only

The first candidate avoided a generic constant King bonus. Each ordinary piece contributed nonlinear promotion proximity:

```text
one rank away   -> 1.0
two ranks away  -> 0.5
three away      -> 1/3
...
already a King  -> 0
```

The participant's proximity margin was added only to nonterminal evaluation. Terminal scoring, legal moves, alpha-beta search, and Crownline rules were unchanged. Weight zero was regression-tested to preserve Baseline A policy across both the original 16-position suite and all 12 King hard cases.

### Root sweep

Weights `0, 25, 50, 100, 200, 400` were inspected at depth 3. The smallest nonzero weight was initially attractive:

| Weight | Early-root changes | King-hard-case changes | Preserved cycle moves selected d2 | Preserved cycle moves selected d3 |
| ---: | ---: | ---: | ---: | ---: |
| 0 | 0 / 16 | 0 / 12 | 4 / 4 | 3 / 4 |
| **25** | **1 / 16** | **1 / 12** | 4 / 4 | **2 / 4** |
| 50 | 1 / 16 | 1 / 12 | 4 / 4 | 2 / 4 |
| 100 | 1 / 16 | 1 / 12 | 4 / 4 | 2 / 4 |
| 200 | 3 / 16 | 1 / 12 | 4 / 4 | 2 / 4 |
| 400 | 4 / 16 | 1 / 12 | 3 / 4 | 2 / 4 |

At weight 25 the preserved depth-3 cycle changed at one additional decision state while broad frozen-root policy remained almost untouched. That was sufficient to justify a trajectory test, but not a promotion claim.

Evidence: workflow `32057876964`, artifact `9297044722`, artifact SHA-256 `b17b508185cfcba68e915dd32825bfc18720c597372cca36f9068d74162f67a0`. All 122 tests passed before the diagnostic.

## Full trajectories reject the formulation

Weight 25 was then tested at fixed depth 3 over the complete frozen paired trajectory structure.

| Self-play engine | Complete sets | Repetition stops | Complete scenario pairs |
| --- | ---: | ---: | ---: |
| Baseline A | 10 / 16 | 6 | 5 / 8 |
| Promotion proximity w25 | 10 / 16 | 6 | 5 / 8 |

The feature produced **no self-play completion or repetition improvement**.

The direct matchup was substantially worse. Only four scenario pairs completed, and Baseline A won all four paired aggregates. Baseline-minus-candidate paired margins were:

```text
+70, +6, +2, +9
```

Completed-set totals pointed the same direction: Baseline won 7 individual complete sets to the candidate's 3, with aggregate completed score `537` to `374`.

The descriptive strategic metrics are especially important because they reveal a flaw in the feature's meaning. In symmetric self-play, compared with Baseline A, the proximity engine produced:

```text
promotions:          23 -> 20
Crownlines scored:   10 -> 5
capture points:     326 -> 279
```

So an evaluator term intended to value approaching promotion actually produced **fewer promotions** in the measured trajectories.

Evidence: workflow `32058124405`, artifact `9297170988`, artifact SHA-256 `e2859cd4874422e9c4e32768b4f203578afb9ae2e83663951b8c9328a443bbf6`. All 122 tests passed before the trajectory run.

## Why the formulation is structurally wrong

The failure exposes a discontinuity in the feature itself:

```text
ordinary piece one rank from promotion -> proximity value 1.0
same piece after promotion             -> proximity value 0
```

The feature rewards *unrealized* promotion opportunity but erases that reward at the moment the opportunity is realized. Search can therefore prefer preserving a near-promotion piece rather than completing the promotion, depending on the surrounding minimax tradeoff.

That interpretation is consistent with the measured drop in actual promotions. It does not prove every changed move was caused by deliberate "hovering," but it is enough to reject the feature definition on semantic grounds as well as trajectory evidence.

## Decision

1. **Reject pure promotion proximity as an evaluator feature.**
2. **Do not test larger weights as a rescue attempt.** The smallest meaningful weight already lost all four complete paired aggregates to Baseline A, and the feature has a known semantic discontinuity.
3. **Retain `king-v0.1` permanently as a late-game evaluator guardrail.** It solved a real measurement blind spot independently of this failed feature.
4. **Keep p200 exact-history repetition policy as the current 150 ms trajectory control, not as a promoted browser opponent.**
5. **Do not change Crownline's rules or browser AI from this result.**

## Next strategic hypothesis: promotion continuity

The next promotion experiment should represent both unrealized and realized promotion value with no cliff at crowning. A clean candidate is a bounded **promotion maturity** term:

```text
ordinary piece -> mirrored progress toward crown rank, normalized to [0, 1)
King           -> 1.0
```

For example, linear maturity can move smoothly from `6/7` one step before promotion to `1.0` after promotion. This is not intended as a complete model of King utility. It asks a narrower question:

> **Does preserving the value of completed promotion correct the discontinuity without broadly distorting policy?**

That feature should again pass both root guardrails before any trajectory run. Position-sensitive King utility (mobility, line participation, immediate liability, Sovereign option value) should remain separate rather than being bundled into the same weight.
