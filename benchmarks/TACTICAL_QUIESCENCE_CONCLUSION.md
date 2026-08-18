# Tactical Quiescence — Conclusion

Status: **mandatory-capture-only quiescence rejected as the next product-strength improvement; tactical blame-horizon infrastructure retained.**

This experiment followed the first human-decision study. Seven recorded human positions were followed by damaging compound captures. Bounded blame-horizon analysis found an avoidable earlier decision in all seven windows, but the blame point was not always the move immediately before punishment: 3/7 were immediate-move blame and 4/7 were upstream blame one human decision earlier.

That result motivated a narrow search hypothesis rather than a new evaluator weight: when fixed-depth search reaches a leaf whose entire legal turn is capture-forced, continue only that forced capture sequence before evaluating the position.

## Rules correction discovered during the experiment

The first regression test incorrectly described the recorded `e3xc5xa7` response after `b2xd4` as mandatory. Under v1.1 this is false because the capturing piece is a King. Sovereignty releases the whole turn from the mandatory-capture obligation whenever a King has a capture, so non-capturing legal actions coexist with that compound capture.

The implementation was already conservative and correct: `mandatory_capture_actions()` returns actions only when **all** legal actions are captures. The test was corrected to preserve the distinction:

- a Sovereign King capture is legal but is not a mandatory-quiescence node;
- an ordinary-piece-only capture obligation is a mandatory-quiescence node.

This distinction matters because several human-play punishments were King compound captures. Mandatory-capture quiescence therefore cannot be expected to address much of the observed tactical-error family without violating the v1.1 Sovereignty semantics.

## Focused depth sweep

The blame-point-only diagnostic compared deterministic fixed-depth-3 promotion-maturity-w10 search at qdepth 0, 1, and 2. The observed human blame move is intentionally a *bad-move* label here, so improvement would mean the bad move becoming less preferred / lower ranked.

| qdepth | bad move chosen best | bad move top-3 | mean bad-move rank | root changes vs q0 |
|---:|---:|---:|---:|---:|
| 0 | 1/7 | 3/7 | 4.43 | 0 |
| 1 | 1/7 | 3/7 | 4.43 | 1 |
| 2 | 1/7 | 3/7 | 4.57 | 1 |

qdepth 1 changed only one root action and did not improve any headline tactical metric. qdepth 2 again changed only one root relative to q0 and slightly **worsened** mean bad-move rank from 4.43 to 4.57. The one-hypothesis experiment therefore has no evidence that deeper mandatory-capture-only quiescence is solving the human-observed tactical weakness.

The corrected CI probe passed 152 tests and completed the q0/q1/q2 diagnostic successfully.

## Decision

Do **not** add mandatory-capture quiescence to the browser Research / Strong opponent.

Do **not** continue to qdepth 4 merely to search for a favorable result. The tested mechanism has answered the intended question sufficiently:

1. it applies to a narrower tactical class than the human evidence initially suggested because Sovereign King captures are optional, not mandatory;
2. qdepth 1 did not improve the seven blame-point rankings;
3. qdepth 2 did not improve them either and slightly worsened mean rank.

Keep the implementation and evidence because the rules-sensitive distinction is useful and the quiescence module may become relevant to a future search architecture. It simply has not earned product promotion as the present tactical fix.

## What advances

The **tactical blame-horizon method** is the successful result of this branch. It demonstrated that immediate punishment is frequently downstream of an earlier decision, and it produced explicit safe alternatives at the earlier blame points.

The next strategic experiment should therefore return to the second question identified by Human Decision v0.1: **opportunity-adjusted Crownline structure**.

A strong next single-feature hypothesis is *safe King coverage*: retain the useful signal that Kings occupying still-unretired Crownline geometries correlate with successful human/bot construction, but discount coverage that is tactically exposed. This should be defined with one explicit safety measure and tested first on the frozen human suite, then independently on trajectories. Do not bundle cooldown readiness, multi-line optionality, capture safety, and geometry into one score at the outset.

The product opponent remains unchanged:

```text
150 ms iterative deepening
+ structural exact transposition table
+ p200 exact-history repeat policy
+ promotion maturity w10
+ max depth 4
```
