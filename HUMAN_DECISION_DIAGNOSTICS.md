# Human-Guided Engine Diagnostics

Crownline now records enough authoritative state to study human and computer decisions without treating either as automatically correct.

The first frozen human-decision suite is `human-v0.1`. It is derived from two exported v1.1 browser sessions and contains 22 unique canonical CLSN positions in three buckets:

- 7 human tactical-error positions where the next computer reply was a compound capture;
- 7 computer Crownline-construction positions sampled two computer turns before a later scored Crownline;
- 8 human Royal-sweep preparation positions sampled two human turns before each of the eight Royal Crownlines in the first fully instrumented sweep.

The raw browser exports are not committed to the repository. The manifest stores their SHA-256 fingerprints, and the suite stores only the selected canonical positions plus provenance metadata. This keeps the benchmark compact while preserving exact position identity.

## Important interpretation rule

An observed human move is **evidence, not an optimal label**.

The dataset intentionally includes recognized human mistakes. It also includes computer moves that later produced useful Crownline structure. The diagnostic therefore compares choices rather than blindly imitating them.

For every frozen position the diagnostic regenerates all legal move + Crownline-choice actions from CLSN and records:

1. fixed-depth search value under the current promotion-maturity evaluator;
2. the observed action's rank among all legal actions;
3. the current evaluator's top action;
4. immediate reply-capture exposure, including maximum capture legs and capture points;
5. descriptive Crownline-network features after each root action.

The network features are **measurement probes only**. They do not change the evaluator. Current probes include:

- occupied unretired Crownline geometries;
- total piece membership across unretired geometries;
- King membership across unretired geometries;
- two-of-three unretired lines;
- King-supported two-of-three lines;
- cooldown-ready King-supported two-of-three lines;
- standing three-owned unretired lines.

These are deliberately decomposed so a later experiment can test one strategic hypothesis at a time rather than introducing a bundled "Crownline intelligence" score.

## Why fixed-depth search is used here

The browser research opponent uses a 150 ms iterative-deepening budget, structural transposition caching, a p200 repeat-history policy, and promotion maturity w10.

The human-decision diagnostic instead uses deterministic fixed-depth alpha-beta with promotion maturity w10 and **no repeat-history state**. That makes the position comparison reproducible and prevents wall-clock variance or missing trajectory history from being mistaken for an evaluator difference.

The diagnostic is not intended to reproduce the exact browser move on every sampled computer position. It is intended to expose what the current strategic evaluator values in the same position.

## Research loop

The intended loop is:

```text
instrumented human play
        ↓
freeze exact CLSN disagreement / success / mistake positions
        ↓
rank all legal actions under the current evaluator
        ↓
measure tactical exposure and Crownline-network structure
        ↓
state one narrow strategic hypothesis
        ↓
experiment on frozen human positions
        ↓
retest on independent self-play / position suites
        ↓
only then consider product promotion
```

This preserves the same one-hypothesis-per-experiment discipline used in the earlier search-engine and repetition work.
