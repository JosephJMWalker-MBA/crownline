# Crownline AI Benchmark Evidence

This directory preserves compact, auditable results from controlled Crownline engine experiments. Competitive claims should be based on complete paired two-game sets. Diagnostic stops such as exact-state repetition remain evidence but are not scored as wins, losses, or draws.

## Baseline A — depth 2 vs depth 2 repetition diagnostic

**Rules:** Crownline v1.1 Candidate  
**Pairing:** 10 seat-balanced pairs = 20 attempted sets  
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

## Next controlled question

Do **not** change the evaluator yet.

The next experiment should keep Baseline A otherwise identical and compare depth 2 against depth 3. The primary questions are:

1. Does deeper search avoid the 4-ply Baseline A cycle?
2. If it does, what does that cost in search nodes and latency?
3. If it does not, does it reproduce the same cycle or discover a different repetition pathology?

Only after the depth experiment should search engineering or Crownline-specific evaluation features be introduced.
