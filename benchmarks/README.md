# Crownline AI Benchmark Evidence

This directory preserves compact, auditable results from controlled Crownline engine experiments. Competitive claims should be based on complete paired two-game sets. Diagnostic stops such as exact-state repetition remain evidence but are not scored as wins, losses, or draws.

## Current research checkpoint

The sections below preserve the **early benchmark progression** from Baseline A through the first frozen CLSN depth experiments. Their measurements remain part of the evidence chain, but the old "next milestone" language at the end is historical rather than the current frontier.

Subsequent work advanced through search engineering, exact-state trajectory policy, promotion-maturity evaluation, browser-scale composition, human-decision diagnostics, and bounded tactical blame analysis.

The current browser-facing research opponent under the v1.1 Candidate is:

```text
150 ms iterative deepening
+ structural exact transposition table
+ p200 exact-history repeat policy
+ promotion maturity w10
+ max depth 4
```

That composition earned advancement to **human product playtesting** after a measured direct comparison and reversed-role directional confirmation. It remains a research profile rather than a claim of optimal play.

Later hypotheses have continued to use independent promotion gates:

- **Unretired King coverage** changed the intended strategic behavior and increased Crownline seeking, but did not demonstrate greater competitive strength; it was rejected for product promotion.
- **Mandatory-capture-only quiescence** did not improve the frozen human tactical diagnostic and was rejected as the next product-strength change.
- The useful result retained from the latter study is the **tactical blame-horizon** method, which showed that visible punishment is often downstream of an earlier decision rather than the immediately preceding move.

For the later evidence chain, read:

- [`STAGE3_PRODUCT_COMPOSITION_CONCLUSION.md`](STAGE3_PRODUCT_COMPOSITION_CONCLUSION.md)
- [`STAGE3_MATURITY_P200_COMPOSITION_CONCLUSION.md`](STAGE3_MATURITY_P200_COMPOSITION_CONCLUSION.md)
- [`HUMAN_DECISION_V0_1_CONCLUSION.md`](HUMAN_DECISION_V0_1_CONCLUSION.md)
- [`TACTICAL_QUIESCENCE_CONCLUSION.md`](TACTICAL_QUIESCENCE_CONCLUSION.md)

The research rule remains: **a feature must earn promotion; a negative result remains evidence.**

## Deterministic evidence boundary

The current baseline engines are deterministic. Repeating the same engine versions from the same exact starting state does **not** create independent samples; it simply reproduces the same trajectory. A seat-balanced pair is therefore the complete evidence unit for one deterministic starting condition.

The original 10-pair depth-2 symmetry run was still useful: it established exact reproducibility. But after that fact was demonstrated, the 10 copies should not be interpreted as `n=10` independent evidence. Future strength claims need a controlled suite of distinct starting conditions rather than repeated copies of one opening.

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

## Why the first opening suite was superseded

The first deterministic opening-suite experiment correctly diversified Game 1, but the ordinary set transition recreated the standard Game 2 start. That meant several apparently different scenarios converged onto the same deterministic Game 2 trajectory. The run remained useful as a harness diagnostic, but its completed-set results are not used as the primary strength evidence.

The fix was architectural rather than statistical: Crownline now has **CLSN1**, a reversible canonical position notation analogous in purpose to chess FEN. The benchmark fixture now freezes the actual Game 1 and Game 2 positions themselves rather than treating an opening-generation procedure as the identity of a scenario.

`position_suite_v0_1.json` contains eight scenario pairs and **16 unique canonical CLSN1 positions** under the v1.1 `candidate` rules. The quantile-generated move prefixes are retained only as provenance.

## Frozen CLSN position suite v0.1 — depth 2 vs depth 3

**Hypothesis changed:** search depth only  
**Evaluator:** unchanged Baseline A evaluator  
**Rules:** Crownline v1.1 (`candidate`)  
**Fixtures:** 8 scenarios × frozen Game 1 + frozen Game 2 = 16 unique CLSN1 positions  
**Seat balance:** two complete-set legs attempted per scenario

This is the first benchmark whose experimental input matches the actual two-game Crownline competition unit.

Four of the eight scenario pairs completed in both seat-balanced legs. **Depth 3 won all four complete scenario pairs**, with paired A-minus-B margins of `-71`, `-72`, `-81`, and `-47` when depth 2 is Participant A. The mean paired margin was therefore **-67.75**.

Across all 16 attempted sets, **12 sets completed and depth 3 won all 12**. Completed-set aggregate scoring was depth 2 **396** to depth 3 **769**. The other four sets were excluded from competitive scoring because the exact-state repetition diagnostic fired.

The complete scenario pairs were:

| Scenario | Pair winner | A-B paired margin |
| --- | --- | ---: |
| `low-lattice` | Depth 3 | -71 |
| `quarter-cross-a` | Depth 3 | -72 |
| `quarter-cross-b` | Depth 3 | -81 |
| `weave` | Depth 3 | -47 |

The four diagnostic stops occurred in `standard-start`, `high-lattice`, `median-line`, and `full-spread`. Every one was again a **four-ply reversible cycle**, with respectively **29, 18, 20, and 22 immediate legal cycle exits**. Only the standard-start cycle contained a Sovereign opportunity/refusal. Repetition is therefore broader than one special v1.1 mechanic and remains an engine-policy problem rather than a forced game state.

Search cost remained consistent with the earlier depth experiment:

| Engine | Mean decision | Mean search nodes | Max decision | Max nodes |
| --- | ---: | ---: | ---: | ---: |
| Depth 2 | 8.42 ms | 38.8 | 34.19 ms | 120 |
| Depth 3 | 39.63 ms | 165.3 | 282.55 ms | 893 |

Depth 3 used about **4.26×** as many search nodes per decision and about **4.71×** the wall-clock decision time.

Other descriptive event counts also moved strongly toward depth 3: 389 vs 238 capture points, 20 vs 7 quota triggers, and 5 vs 3 scored Crownlines. Promotions were exactly even at 33 each. These are trajectory-level descriptors of the frozen suite, not independently randomized population estimates.

The compact auditable evidence is stored in [`position_v0_1_d2_vs_d3_summary.json`](position_v0_1_d2_vs_d3_summary.json). The frozen benchmark inputs are stored in [`position_suite_v0_1.json`](position_suite_v0_1.json).

## Historical next-milestone note

The original version of this checkpoint identified **depth 2 vs depth 4 on the frozen CLSN v0.1 suite** as the next clean experiment and instructed the project not to change the evaluator yet. That was correct at this point in the research sequence and is preserved as historical methodology.

That milestone has since been superseded by the later Stage 2/Stage 3 work linked at the top of this file. Do not use this old checkpoint as the present implementation roadmap.
