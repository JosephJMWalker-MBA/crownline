# Stage 3 Maturity + p200 Composition Conclusion

This document closes the first measured composition of Crownline's two independently justified Stage-3 improvements under v1.1 (`candidate`) rules:

- **trajectory handling:** p200 exact-history repeat preference;
- **strategic evaluation:** promotion maturity w10.

Both run on the Stage-2 150 ms iterative-deepening + structural exact-TT search substrate. The browser opponent remains unchanged by these experiments.

## 1. Composition boundary

The candidate changes exactly one strategic dimension relative to the current p200 control:

```text
control:   iterative TT + p200 exact-history policy
candidate: iterative TT + p200 exact-history policy + promotion maturity w10
```

Regression tests establish both composition boundaries with a non-expiring clock:

1. `repeat_penalty=0` preserves the measured maturity-only iterative structural-TT search;
2. `maturity_weight=0` preserves the p200 product search on first-visit states.

The game rules, legal moves, alpha-beta semantics, structural TT semantics, and tie-breaking remain unchanged.

## 2. Symmetric 150 ms composition run

The first run compared p200 self-play, p200+maturity self-play, and direct p200 vs p200+maturity play.

Self-play moved modestly in the expected direction:

| Engine | Complete sets | Repetition stops | Complete scenario pairs | Mean completed depth |
| --- | ---: | ---: | ---: | ---: |
| p200 control | 9 / 16 | 7 | 4 / 8 | ~3.30 |
| p200 + maturity w10 | 10 / 16 | 6 | 4 / 8 | ~3.31 |

The maturity feature therefore did not impose a measurable search-depth penalty in this run and improved completion by one set while removing one repetition stop.

The direct matchup was much stronger. With p200 control as Participant A and the composed candidate as Participant B:

```text
complete sets:          12 / 16
repetition stops:        4
complete scenario pairs: 5 / 8
paired result:            control 0 / composed 4 / draws 1
paired A-B margins:      -76, -160, 0, -105, -14
individual set wins:      control 4 / composed 8
completed-set score:      control 777 / composed 1214
mean paired A-B margin:  -71
```

All four decisive complete pairs favored the composed candidate.

Evidence: `benchmarks/stage3_maturity_p200_composition_150ms.json`.

## 3. Reversed-role confirmation

Because 150 ms search is deadline-sensitive, one favorable run was not treated as sufficient for product advancement. A second direct matchup reversed the engine assignment to Participants A/B while retaining every scenario's normal two-leg seat balance.

This time the composed candidate was Participant A and p200 control was Participant B:

```text
complete sets:          13 / 16
repetition stops:        3
complete scenario pairs: 5 / 8
paired result:            composed 4 / control 0 / draws 1
paired A-B margins:       +4, +41, 0, +105, +46
individual set wins:      composed 8 / control 5
completed-set score:      composed 1164 / control 843
mean paired A-B margin:  +39.2
```

Again, every decisive complete scenario pair favored the composed candidate.

Evidence: `benchmarks/stage3_maturity_p200_confirmation_150ms.json`.

## 4. Replicated directional result

Across the two deadline-sensitive direct runs:

- 10 complete seat-balanced scenario-pair observations survived the repetition filter;
- composed p200+maturity won **8**;
- **2** drew;
- p200 control won **0**;
- 25 individual sets completed, with composed winning **16** and control **9**;
- the summed paired margin across the ten complete pairs favored composed by **551 points**, or **55.1 points per complete pair**.

These are not ten independent starting conditions: the second run repeats the same frozen scenario suite under a deadline-sensitive runtime and reverses engine assignment. They should therefore be interpreted as a **replication of direction**, not as a population win-rate estimate.

That distinction matters. The result is stronger than a single run because the direction survived runtime variation and participant reversal, but it does not imply Crownline is solved or that the measured margin generalizes to arbitrary future positions.

## 5. Product-gate decision

The evidence now supports advancing the composed engine to **human product playtesting**.

Why it passes this gate:

1. promotion maturity first passed fixed-depth root and trajectory tests;
2. its characteristic King hard-case policy difference remained perfectly stable in repeated 150 ms tests;
3. composing maturity with p200 slightly improved self-play completion rather than degrading it;
4. the direct product-regime matchup favored the composition 4-0-1 in complete pairs;
5. the reversed-role confirmation independently reproduced a 4-0-1 paired result;
6. neither run showed a material completed-depth penalty from maturity.

What this gate does **not** mean:

- the composed engine is not proven optimal;
- p200 and w10 are not universal constants;
- repetition is not fully solved;
- the browser default should not silently change without a human playtest;
- incomplete scenario pairs remain diagnostic evidence, not competitive results.

## 6. Next step

The next measured step is no longer another evaluator weight sweep. It is a controlled human-facing integration:

> Add the composed `150 ms + structural TT + p200 + maturity w10` opponent as an explicit **Research / Strong** AI option while preserving the current Baseline A opponent.

That allows direct human comparison without losing the reproducible baseline. The first playtest questions should be qualitative but concrete:

- Does the stronger engine feel less repetitive?
- Does it create and deny promotions more intelligently?
- Does it use Kings in ways that feel purposeful rather than merely mobile?
- Does it produce strategically surprising moves that remain explainable from the measured feature set?
- Is ~150 ms decision latency comfortable in the browser experience?

Human feedback should be logged separately from benchmark evidence. A favorable human playtest can then justify making the stronger engine the default opponent.

No Crownline rule change is implied by this result.
