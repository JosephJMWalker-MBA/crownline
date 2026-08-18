# Human Decision v0.1 — Conclusion

Status: **King coverage hypothesis rejected for product promotion; human-decision suite retained as research infrastructure.**

This study began with two instrumented Crownline v1.1 browser sessions rather than self-play alone. The source sessions contained 1,457 recorded moves across 12 games. The frozen `human-v0.1` diagnostic suite selected 22 exact canonical CLSN positions in three intentionally different evidence buckets:

- 7 recognized human tactical-error positions followed by compound captures;
- 7 computer Crownline-construction positions sampled two computer turns before a later scored Crownline;
- 8 human preparation positions sampled two human turns before each Royal Crownline in the first fully instrumented eight-Royal sweep.

Observed human moves are not treated as optimal labels. The suite contains known mistakes on purpose.

## What the first diagnostic showed

Under deterministic fixed-depth-3 alpha-beta with promotion maturity w10 and no trajectory-history policy:

- bot Crownline-construction moves matched the evaluator's best action in 5/7 positions and ranked top-three in 6/7;
- human Royal-sweep preparation moves matched best in only 2/8, but ranked top-three in 5/8;
- recognized human tactical-error moves matched best in 3/7 and ranked top-three in 4/7.

The tactical bucket produced an important blame-horizon result. Only 3/7 recognized error positions had a strictly safer legal root action under the simple immediate compound-capture exposure metric. In the other 4/7 positions, the sampled move was already forced or equally exposed by that local metric. Therefore a useful tactical-learning tool must backtrack through earlier human decisions rather than assuming the move immediately before the punishment caused the mistake.

The strongest common descriptive signal in both successful strategic buckets was **King membership across still-unretired Crownline geometries**. Compared with the current evaluator's preferred root action, observed bot-construction moves averaged +0.57 King line-membership units and Royal-sweep preparation moves averaged +0.63. This motivated one narrow evaluator hypothesis instead of a bundled strategy score.

## Hypothesis tested: unretired King coverage

The experimental feature counts a King once for every still-unretired Crownline geometry containing its square. Retired lines contribute zero. The evaluator adds only the participant coverage margin, leaving ordinary-piece geometry, two-of-three threats, cooldown readiness, capture safety, future reachability, and trajectory memory untouched.

This feature behaved as intended on the human diagnostic suite.

At coverage weight 160:

- bot-construction best-action matches improved from 5/7 to 6/7;
- all 7 bot-construction observations ranked top-three;
- combined strategic-positive best matches improved from 7/15 to 8/15;
- combined strategic-positive top-three improved from 11/15 to 12/15;
- mean strategic-positive rank improved from 3.33 to 2.80.

Weight 200 improved mean strategic-positive rank slightly further to 2.73 while preserving 8/15 best matches and 12/15 top-three. Higher weights exposed the limit of the feature: at 320 the strategic best-match count fell to 4/15, and at 400 to 3/15. Pure coverage can therefore become actively distorting when overweighted.

## Independent trajectory gate

The local human-position improvement did **not** establish playing strength, so weights 200 and 160 were tested independently over the frozen 8-scenario / 16-set v0.1 trajectory suite against the promotion-maturity-w10 control.

### Coverage w200

Self-play completion improved from 12/16 sets with 4 repetition stops to 14/16 with 2 repetition stops. The coverage engine's symmetric self-play completed 7/8 scenario pairs.

However, direct control-vs-coverage evidence did not show a strength gain. Among 5 complete scenario pairs, control won 1 and 4 were aggregate draws; coverage won none. Across the 12 individually completed sets, control led 7–5 and 608–580 in aggregate completed-set score. Coverage did score more Crownlines (10 vs 6) but fewer capture points (302 vs 336).

Interpretation: w200 successfully changed *what the engine sought*, but it traded tactical/capture value for geometry rather than producing a stronger policy.

### Coverage w160

The smaller weight did not rescue the hypothesis. Candidate self-play was identical to the control on the headline completion diagnostic: 12/16 completed sets, 4 repetition stops, and 6 complete scenario pairs.

In direct control-vs-coverage play, only 10/16 sets completed because 6 stopped on repetition. The 4 complete scenario pairs were all aggregate draws, so there is no paired strength win for either side. Among the completed individual sets, control led 6–4 and 511–445 in aggregate score. Coverage again produced many more Crownlines (14 vs 7) while fewer capture points were recorded (274 vs 298).

This repeats the w200 pattern more strongly: the feature is a real Crownline-seeking signal, but **more Crownlines is not equivalent to stronger Crownline play**.

## Decision

Do not add unretired King coverage to the browser Research / Strong opponent. Keep the experimental code and evidence because the feature is informative and may become useful as a component of a better-defined future concept, but the pure feature has failed the independent playing-strength gate.

Do not continue lowering or tuning the coverage weight merely to search for a favorable result. The tested family has answered the scientific question sufficiently: local human alignment transferred into increased Crownline production, but not into demonstrated competitive strength.

The production research opponent therefore remains:

```text
150 ms iterative deepening
+ structural exact transposition table
+ p200 exact-history repeat policy
+ promotion maturity w10
+ max depth 4
```

## What the human data taught us anyway

The experiment was still successful as a research loop. Human play exposed a measurable strategic signal that self-play had not isolated; the signal became a single formal hypothesis; the hypothesis moved the intended behavior; and independent trajectories prevented us from mistaking behavioral imitation for stronger play.

Two next research questions now have better justification than raw coverage:

1. **Tactical blame horizon** — for compound-capture mistakes, identify the earliest human decision after which a damaging multi-jump becomes unavoidable or materially harder to avoid.
2. **Opportunity-adjusted Crownline structure** — distinguish geometry that remains competitively useful from geometry purchased at excessive tactical cost. Any next feature should still isolate one factor at a time; for example, safe King coverage or cooldown-ready multi-line optionality, not a bundled strategic score.

The first of these is infrastructure/diagnostic work and can be pursued without changing the bot. The second should wait until the blame-horizon analysis is complete enough to tell us how tactical safety and Crownline construction interact.
