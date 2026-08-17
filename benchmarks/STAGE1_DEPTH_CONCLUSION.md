# Stage 1 Conclusion — Pure Search Depth

Stage 1 asked one narrow question under Crownline v1.1 (`candidate`):

> **What does additional fixed minimax depth buy when the evaluator, rules, position fixtures, seat balance, and repetition diagnostic remain unchanged?**

The answer is now measured across the frozen CLSN1 position suite rather than inferred from one opening.

## Experimental boundary

The suite contains eight scenarios, each with a frozen Game 1 and Game 2 CLSN1 fixture: **16 unique canonical positions** total. Each matchup attempts two complete Crownline sets per scenario, reversing the Game-1 participant seat between the two legs.

Exact-state repetition is a diagnostic stop, not a game rule. A stopped set is retained as evidence and excluded from competitive scoring.

## Results at a glance

| Matchup | Complete scenario pairs | Complete sets | Repetition stops | Stronger-depth complete pair record | Mean nodes / decision | Mean ms / decision |
| --- | ---: | ---: | ---: | --- | --- | --- |
| d2 vs d3 | 4 / 8 | 12 / 16 | 4 | d3 4–0 | 38.8 vs 165.3 | 8.42 vs 39.63 |
| d2 vs d4 | 4 / 8 | 11 / 16 | 5 | d4 4–0 | 40.1 vs 706.7 | 8.91 vs 168.23 |
| d3 vs d4 | 2 / 8 | 8 / 16 | 8 | d4 2–0 | 163.8 vs 785.1 | 33.66 vs 162.11 |

The complete paired margins were:

- d2 vs d3: `-71, -72, -81, -47` from d2's perspective;
- d2 vs d4: `-59, -51, -91, -73` from d2's perspective;
- d3 vs d4: `-46, -15` from d3's perspective.

## What Stage 1 supports

### 1. Depth 3 is a meaningful strength improvement over depth 2

Across the four scenario pairs that completed in both seat-balanced legs, depth 3 won all four. Across individual completed sets, depth 3 won all 12. Completed-set aggregate scoring was 769–396 in depth 3's favor.

The cost was approximately **4.26× search nodes** and **4.71× wall-clock decision time** relative to depth 2 on that CI run.

This is the cleanest fixed-depth improvement found in Stage 1: substantial apparent strength at an interactive absolute latency.

### 2. Depth 4 is stronger-looking than depth 2, but much more expensive

Depth 4 won all four complete scenario pairs and all 11 completed individual sets against depth 2. Completed-set aggregate scoring was 735–347.

The cost was approximately **17.62× search nodes** and **18.88× wall-clock decision time** relative to depth 2. A maximum depth-4 decision exceeded 1.5 seconds on the CI runner.

### 3. Depth 4 shows only a modest direct advantage over depth 3 on completed evidence

The direct d3-vs-d4 experiment is necessary because opponent policy changes the trajectory; separate matches against depth 2 cannot rank depth 3 and depth 4 cleanly.

Only two of eight scenario pairs completed in both legs. Depth 4 won both paired aggregates, with margins of 46 and 15 points. Of the eight completed individual sets, depth 4 won seven and depth 3 won one.

Depth 4 cost approximately **4.79× search nodes** and **4.82× wall-clock time** relative to depth 3.

That is evidence of some additional strength, but the evidence boundary is much smaller than the d2-vs-d3 comparison because half the attempted sets stopped diagnostically.

## The dominant finding: depth does not solve repetition

Across all three frozen-suite experiments, every detected exact-state repetition was a **four-ply reversible cycle**. The cycles repeatedly contained many legal actions that immediately left the cycle.

Repetition stops did not decrease monotonically with depth:

```text
d2 vs d3: 4 / 16 sets
d2 vs d4: 5 / 16 sets
d3 vs d4: 8 / 16 sets
```

The identities of the repeating scenarios also changed with the matchup. Some cycles contained a Sovereign opportunity or refusal; many did not. The pathology therefore cannot be reduced to the v1.1 Sovereignty mechanic.

The consistent evidence is:

> **The current evaluator/search policy is willing to choose reversible cycles even when many immediate legal exits exist. Additional fixed depth changes which cycles appear but does not reliably remove them.**

## Stage 1 decision

**Do not increase the browser bot to fixed depth 4 as the next product change.**

Depth 4 is materially more expensive than depth 3 and does not address the dominant failure mode. Depth 3 remains the most promising fixed-depth point observed so far, but no browser-default change is justified solely by these experiments because the next stage may improve search efficiency first.

Stage 1 is complete.

## Stage 2 boundary

Stage 2 should improve **search engineering while preserving the evaluator**. The first experiments should be designed so we can distinguish computational efficiency from playing-policy changes.

A strong first hypothesis is exact transposition caching:

> **Can exact-state transposition caching reduce expanded search work without changing any chosen move?**

For a clean first implementation:

- Baseline A remains unchanged;
- cache keys derive from canonical CLSN1 plus search depth and participant/seat perspective;
- only exact fully searched node values are reusable; alpha-beta cutoff bounds are not cached as exact values;
- tests must prove action equivalence with the baseline on representative positions;
- the benchmark must record cache hits separately from expanded nodes;
- any playing-strength claim waits until an efficiency-preserving implementation is established.

If exact caching earns its place, later Stage 2 experiments can isolate move ordering, iterative deepening, and time-budgeted search before Crownline adds domain-specific evaluation features.

## Evidence files

- `position_v0_1_d2_vs_d3_summary.json`
- `position_v0_1_d2_vs_d4_summary.json`
- `position_v0_1_d3_vs_d4_summary.json`
- `position_suite_v0_1.json`

These summaries preserve source fingerprints so the evidence remains attributable as the engine and harness evolve.
