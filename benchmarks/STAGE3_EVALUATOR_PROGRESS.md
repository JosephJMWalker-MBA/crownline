# Stage 3 Progress — Evaluator Experiments

Stage 3 asks a different question from the completed search-engineering work:

> **What Crownline-specific information is Baseline A missing when it assigns value to a position?**

The first target is the empirically observed reversible-cycle pathology. All work in this document uses Crownline v1.1 (`candidate`) rules. The browser opponent remains unchanged.

## 3.0 — Diagnose before changing the evaluator

The original preserved depth-2 Game-1 repetition was reconstructed exactly from CLSN1 and replayed as the four-ply cycle:

```text
White  d6-e5
Black  b4-c3
White  e5-d6
Black  c3-b4
```

The experiment measured every legal root action at depths 2, 3, and 4 rather than assuming deterministic lexicographic tie-breaking was creating the loop.

The result falsified that simple explanation. At depth 2 the recorded cycle move was the **unique minimax-best action at all four decision states**, beating the best immediate escape by 299, 799, 199, and 199 evaluator points respectively. At depth 3 two of the four preferences became very narrow (+3 and +1), while depth 4 produced two ties and two strict cycle preferences.

Therefore:

> **The repetition pathology is not primarily a tie-break bug. Baseline A often assigns materially higher minimax value to the reversible cycle itself.**

That matters because an anti-tie workaround would hide the symptom without changing the mistaken valuation.

Evidence: workflow run `32045713370`, artifact `9292837055`, artifact SHA-256 `5da60202ef0ec373045e16aae7df59be21a112a0c43be6a19f1104a793c48a19`.

## Why provisional board score became the first hypothesis

Baseline A's nonterminal evaluator begins with:

```text
current score margin × 100
```

The authoritative game score is:

```text
capture bank + current board-square value + banked Crownline bonus
```

Capture-bank points and banked Crownline points are irreversible. Current board-square value is not: a piece can move from one square value to another and then return on a later turn.

In the preserved cycle, those reversible square-value changes can move the static evaluation by hundreds of points. This made a clean first hypothesis possible: perhaps Baseline A was treating provisional location score too much like already-realized score.

## 3.1 — Isolate nonterminal board-value weight

An experimental evaluator separated the score into:

```text
durable score = capture bank + banked Crownline bonus
provisional score = current board-square value
```

Only provisional board value was varied. Everything else stayed fixed:

- Crownline rules and final scoring;
- capture-bank weighting;
- already-banked Crownline weighting;
- terminal evaluation;
- mobility term;
- search depth and alpha-beta semantics;
- deterministic tie-breaking.

`board_weight = 1.0` is algebraically Baseline A and was regression-tested for static-value and action equivalence on the frozen CLSN position suite.

Weights `1.00, 0.75, 0.50, 0.25, 0.00` were tested at depths 2, 3, and 4 against two preserved four-ply cycles, eight decision states total.

The strongest diagnostic point was `board_weight = 0.25` at depth 3/4:

- preserved cycle choices fell from `6/8` to `3/8`;
- only `2/16` frozen-suite root actions changed at depth 3;
- only `2/16` frozen-suite root actions changed at depth 4.

By contrast, removing board value entirely nearly eliminated the preserved cycle choices but changed `7/16` frozen actions at depth 3/4, making it much more disruptive.

This made `0.25` a reasonable **candidate for a trajectory test**, not a promoted evaluator.

Evidence: workflow run `32045989893`, artifact `9292944058`, artifact SHA-256 `e26446951eea106a82150447d4ef421399be08ab124931b1b5bb19e04d583027`. All 92 tests passed before the experiment.

## 3.1b — Full trajectories falsify the apparent fix

The `0.25` candidate was then tested at fixed depth 3 over the complete frozen eight-scenario / sixteen-position benchmark structure.

Three matchups were run:

```text
Baseline d3 vs Baseline d3
Board-weight 0.25 d3 vs Board-weight 0.25 d3
Baseline d3 vs Board-weight 0.25 d3
```

The primary self-play comparison was decisive in the wrong direction:

| Self-play engine | Complete sets | Repetition stops | Complete scenario pairs |
| --- | ---: | ---: | ---: |
| Baseline d3 | 10 / 16 | 6 | 5 / 8 |
| Board-weight 0.25 d3 | 8 / 16 | 8 | 4 / 8 |

The candidate **increased** repetition stops from 6 to 8. In the head-to-head matchup only 7 of 16 sets completed and 9 stopped on repetition, so there is no basis for a playing-strength promotion either.

This is an important negative result:

> **Reducing provisional board-square weight can break known cycle decisions locally while creating new cycles elsewhere. The pathology was displaced, not solved.**

The board-weight hypothesis is therefore rejected as a general anti-cycle fix. No browser or production evaluator change should be made from it.

Evidence: workflow run `32046325488`, artifact `9293079718`, artifact SHA-256 `f921d1127f5330c06bb0f21f5cf300c9a6bbd8bb57aa8090877204c005a7d05a`. All 92 tests passed before the trajectory run.

## A stronger common signal emerged

The full-trajectory evidence gives us a better clue than board weight.

Every detected cycle in all three Stage-3 trajectory matchups was again exactly four plies long. More importantly, **every one of the moving pieces in every detected cycle was already a King**. The loops have the same structural form:

```text
King A moves X → Y
King B moves U → V
King A moves Y → X
King B moves V → U
```

Baseline self-play produced three distinct repeated trajectories duplicated by seat symmetry. The `0.25` candidate produced four distinct repeated trajectories. The asymmetric head-to-head produced nine repetition stops. Across them, Sovereignty was sometimes involved and sometimes absent, so Sovereignty alone is not the common cause.

This narrows Stage 3 substantially. A simple constant "King bonus" would not help because it does not distinguish two squares occupied by the same already-crowned King. What is missing must describe **what a King is accomplishing from its position**, not merely whether a King exists.

## Stage 3.2 boundary

The next evaluator experiment should therefore remain state-based and Crownline-specific before we add explicit repetition memory.

The strongest next hypothesis is **Crownline construction / denial pressure**:

> A King position has strategic value when it contributes to an available Crownline geometry, helps create a near-complete King-gated line, blocks an opponent's available line, or preserves access to an unretired scoring geometry. Baseline A currently sees only realized meld points and current square value, not this latent line structure.

This feature should be introduced independently and inspected first on:

1. the frozen 16-position CLSN suite;
2. the preserved repetition states;
3. then complete frozen-suite trajectories.

If Crownline-pressure valuation does not reduce repetition without unacceptable policy disruption, the evidence will then justify moving from a purely state-based evaluator to explicit trajectory context such as repetition-aware search preference. That would remain an **AI policy**, not a Crownline game rule, unless the rules are separately changed.

The measurement discipline remains the same: one hypothesis at a time, preserve failures, and do not promote a browser change from root-position anecdotes alone.
