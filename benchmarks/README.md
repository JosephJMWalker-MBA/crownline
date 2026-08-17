# Crownline AI Benchmark Evidence

This directory preserves compact, auditable results from controlled Crownline engine experiments. Competitive claims should be based on complete paired two-game sets. Diagnostic stops such as exact-state repetition remain evidence but are not scored as wins, losses, or draws.

## Deterministic evidence boundary

The current baseline engines are deterministic. Repeating the same engine versions from the same exact starting state does **not** create independent samples; it simply reproduces the same trajectory. A seat-balanced pair is therefore the complete evidence unit for one deterministic starting condition.

The original 10-pair depth-2 symmetry run was still useful: it established exact reproducibility. But after that fact was demonstrated, the 10 copies should not be interpreted as `n=10` independent evidence. Future strength claims need a controlled suite of distinct starting conditions/opening scenarios rather than repeated copies of one opening.

## Baseline A — depth 2 vs depth 2 repetition diagnostic

**Rules:** Crownline v1.1 Candidate  
**Pairing:** 10 reproduced seat-balanced pairs = 20 attempted sets  
**Engines:** identical deterministic Baseline A at depth 2  
**Repetition diagnostic:** third occurrence of an exact future-relevant state  
**Result:** 0 complete sets; all 20 stopped on exact-state repetition in Game 1

Every run reproduced a **4-ply cycle**. In the representative A-first leg, the triggering position first appeared at ply 66, repeated at ply 70, and was detected for the third time at ply 74:

```text
71  White  d6-e5
72  Black  b4-c3
73  White  e5-d6
74  Black  c3-b4
```

The cycle did **not** involve Sovereign opportunities or refusals.

Most importantly, the loop was not forced by the rules. Across the four decision states in the detected cycle, the engine had:

| Ply | Side | Legal actions | Immediate cycle exits |
| --- | --- | ---: | ---: |
| 70 | White | 6 | 5 |
| 71 | Black | 9 | 8 |
| 72 | White | 5 | 4 |
| 73 | Black | 8 | 7 |

So at every decision state, exactly one legal action kept the position inside the four-state cycle, and Baseline A repeatedly selected it. There were **24 immediate escape actions** across the cycle.

This sharply narrows the diagnosis: the observed failure is a **search/evaluation/policy-selection pathology**, not an unavoidable rules loop and not a Sovereignty-specific behavior.

The representative repeated state had capture banks White 6 / Black 7 and a provisional participant score of A 19 / B 46 in the A-first leg. No capture quota had been triggered.

The compact machine-readable evidence is stored in [`baseline_d2_vs_d2_repetition_summary.json`](baseline_d2_vs_d2_repetition_summary.json), including the canonical state fingerprint, source SHA-256 fingerprints, cycle moves, repeated board state, search metrics, and representative escape actions.

## Depth 2 vs depth 3 — first controlled search-depth experiment

**Hypothesis changed:** search depth only  
**Evaluator:** unchanged Baseline A evaluator  
**Pairing:** one seat-balanced pair = two attempted sets  
**A:** depth 2  
**B:** depth 3

The result is promising but deliberately not promoted to a win-rate claim.

One set completed. Depth 3 won **both games** and the complete two-game set **63–27**. In the other leg, depth 3 won Game 1 **29–13**, but Game 2 entered another exact 4-ply cycle and the set was therefore excluded from competitive scoring.

Across the complete and partial trajectories, depth 3 earned 55 capture points versus depth 2's 27 and triggered the capture quota three times versus zero for depth 2. Those event counts are descriptive for this trajectory, not population estimates.

The computational cost was substantial but still small in absolute interactive terms on the CI runner:

| Engine | Mean decision | Mean search nodes | Max decision | Max nodes |
| --- | ---: | ---: | ---: | ---: |
| Depth 2 | 11.07 ms | 48.2 | 27.58 ms | 110 |
| Depth 3 | 52.17 ms | 202.9 | 123.03 ms | 454 |

Depth 3 therefore used about **4.21×** as many search nodes per decision and about **4.71×** the wall-clock decision time in this run.

### Remaining repetition

The remaining cycle occurred in **Game 2**, not Game 1. The repeated state first appeared at ply 62, repeated at 66, and triggered the diagnostic at 70:

```text
67  Depth 3 / White  c4-d5
68  Depth 2 / Black  b3-a4
69  Depth 3 / White  d5-c4
70  Depth 2 / Black  a4-b3
```

Unlike the depth-2 symmetry cycle, this one included a **Sovereign opportunity and refusal** on the depth-3 move `c4-d5`.

It was still not forced. The four decision states contained **29 immediate cycle-exit actions** in total:

| Ply | Side | Legal actions | Immediate cycle exits |
| --- | --- | ---: | ---: |
| 66 | Depth 3 / White | 7 | 6 |
| 67 | Depth 2 / Black | 10 | 9 |
| 68 | Depth 3 / White | 7 | 6 |
| 69 | Depth 2 / Black | 9 | 8 |

So one extra ply materially changed play and produced a complete, decisive set in one seat-balanced leg, but **depth alone did not remove the reversible-cycle pathology**.

The compact evidence is stored in [`depth2_vs_depth3_diagnostic_summary.json`](depth2_vs_depth3_diagnostic_summary.json).

## Next measurement milestone

Before making a stronger statistical claim, build a deterministic **scenario/opening suite**. Each scenario should have a stable identifier and canonical starting-state fingerprint, and each engine comparison should use the same suite with seat balance preserved.

That gives future experiments multiple genuinely distinct trajectories while retaining reproducibility. Once the suite exists, depth 2 vs depth 3 can be rerun across it before changing the evaluator or introducing search-engineering improvements.
