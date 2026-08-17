# Stage 3 Cycle Conclusion — Static Evaluation vs Trajectory Context

This document closes the first Stage 3 problem under Crownline v1.1 (`candidate`):

> **Why does Baseline A enter reversible four-ply King cycles, and what is the smallest measured intervention that reduces them without changing Crownline's rules?**

The browser opponent remains unchanged. Every repetition stop in these experiments is a benchmark diagnostic, not a game rule.

## 1. The cycle is a valuation problem, not merely a tie-break problem

The original preserved depth-2 cycle was reconstructed exactly from CLSN1 and every legal root action was evaluated at depths 2, 3, and 4.

At depth 2 the recorded cycle action was the **unique minimax-best action at all four states**, exceeding the best immediate escape by 299, 799, 199, and 199 evaluator points respectively. Deeper search narrowed some of those gaps but did not eliminate the general pathology.

Therefore the deterministic lexicographic tie-break is not the primary cause. Baseline A can genuinely value the reversible cycle more highly than its immediate exits.

Evidence: workflow `32045713370`, artifact `9292837055`, SHA-256 `5da60202ef0ec373045e16aae7df59be21a112a0c43be6a19f1104a793c48a19`.

## 2. Static evaluator fixes can displace cycles instead of solving them

### Provisional board-square weight

Baseline A treats current board-square value as part of its dominant score-margin term even though that value is provisional until the game ends. Reducing only that nonterminal term looked promising at individual preserved cycle states: `board_weight=0.25` reduced selected cycle actions while changing only a small number of frozen root decisions.

Full trajectories falsified the apparent fix. At depth 3:

| Self-play engine | Complete sets | Repetition stops | Complete scenario pairs |
| --- | ---: | ---: | ---: |
| Baseline A | 10 / 16 | 6 | 5 / 8 |
| Board weight 0.25 | 8 / 16 | 8 | 4 / 8 |

The candidate broke known loops locally and created more elsewhere.

Evidence: workflow `32046325488`, artifact `9293079718`, SHA-256 `f921d1127f5330c06bb0f21f5cf300c9a6bbd8bb57aa8090877204c005a7d05a`.

### Crownline construction / denial pressure

The next state-based experiment added latent Crownline geometry: open unretired lines, owned nodes, owned pairs, and King-gated line participation. This was deliberately a transparent geometric term rather than an opaque strategic bundle.

At depth 3, a pressure weight of 100 changed only `2/16` frozen root actions but did **not** improve self-play repetition: `6 -> 6` stops. A stronger weight of 200 reduced repetition from `6 -> 4`, but head-to-head evidence against Baseline A was poor: only five scenario pairs completed, and Baseline A won four of those paired aggregates to the pressure engine's one.

The stronger pressure engine also scored fewer Crownlines in self-play despite explicitly valuing latent line structure, another warning that the feature was distorting tradeoffs rather than simply teaching useful geometry.

The line-pressure feature is therefore retained as useful experimental evidence, but **not promoted**.

Pressure-200 evidence: workflow `32047285203`, artifact `9293392306`, SHA-256 `eb8143349324edbd6f7ef2557aeeead2f3ee9ef72bb40835e09f09215b0244f3`.

Pressure-100 evidence: workflow `32047614323`, artifact `9293517152`, SHA-256 `b7989d9c9240a64c3358ecd26c594597e9cbc34dabe76a6639d8e8992c4fe759`.

## 3. Why exact repetition requires trajectory information

The experiments exposed a useful boundary between **position quality** and **trajectory quality**.

A static evaluator is a function of the current state:

```text
V = f(CLSN)
```

If a four-ply sequence returns to the exact same CLSN, every future-relevant game fact represented by that state is identical. A purely state-based evaluator therefore cannot know whether this is the first visit, second visit, or twentieth visit unless history is supplied separately.

Static strategic features can make a particular loop less attractive indirectly, but they cannot represent the fact **"we have already been here."** That fact belongs to the trajectory, not the position.

This justified one deliberately narrow history-aware experiment before adding more evaluator features.

## 4. Stage 3.3 — Minimal actual-history repeat preference

`RepeatAwareEngine` preserves Baseline A's evaluator, recursive minimax search, legal moves, and deterministic tie-breaking. It adds one root-level policy only:

> If a candidate move recreates an exact CLSN afterstate that the same participant has previously produced in the current game, subtract a configurable penalty from that root action's minimax value.

The repeated move remains legal and may still be selected when its minimax advantage is larger than the penalty. This is therefore neither a repetition ban nor a Crownline rule.

The engine remembers only exact afterstates it actually produced during the current game and automatically clears that memory at a Game-1/Game-2 or new-scenario boundary.

A zero penalty is a control and preserves Baseline A policy on the frozen CLSN suite.

### Penalty sweep

Five penalties were tested in symmetric depth-3 self-play over the frozen eight-scenario suite:

| Repeat penalty | Complete sets | Repetition stops | Complete scenario pairs | Other harness stops |
| ---: | ---: | ---: | ---: | --- |
| 0 | 10 / 16 | 6 | 5 / 8 | none |
| **50** | **14 / 16** | **2** | **7 / 8** | none |
| 100 | 12 / 16 | 4 | 6 / 8 | none |
| 200 | 14 / 16 | 2 | 7 / 8 | none |
| 500 | 12 / 16 | 2 | 6 / 8 | **2 ply caps** |

The result is intentionally non-monotonic: a larger penalty does not simply produce a better engine. Different penalties change the trajectory and therefore which future repetition opportunities arise.

Penalty 50 is the strongest first candidate because it is the **smallest tested intervention** that reduced repetition from six stops to two without introducing another harness pathology. In the same self-play run it also produced more capture points, Crownlines, and promotions than the zero-penalty control; those are descriptive trajectory changes, not independent strength claims.

Evidence: workflow `32048160593`, artifact `9293766732`, SHA-256 `a53503c0496aaaeca580f442aee93f43a5518a33ebd161d788557a14ad6f3fe2`. All 100 tests passed before the sweep.

### Penalty 50 vs Baseline A

The minimal candidate was then tested directly against depth-3 Baseline A with the same seat-balanced scenario structure.

Results:

```text
complete sets:          11 / 16
repetition stops:        5
complete scenario pairs: 5 / 8
paired result:           0 Baseline wins / 0 candidate wins / 5 draws
individual complete sets: Baseline 5 / candidate 6
completed-set score:    Baseline 553 / candidate 585
```

The five complete scenario pairs all drew in aggregate, so the evidence does **not** support claiming the repeat-aware candidate is stronger than Baseline A. It also does not show a paired strength loss on the completed evidence.

The mixed matchup still had five repetition stops because only one of the two engines had trajectory awareness. A repeat-aware participant cannot force a memoryless opponent to value repetition differently.

Evidence: workflow `32048706427`, artifact `9293856816`, SHA-256 `a2d3b9b218f6d60b8d3ea5a286f0a36bec3250d321cc660ad1593d2ed4cb7a21`. All 100 tests passed before the head-to-head run.

## Decision

The Stage 3 cycle evidence supports the following conclusions:

1. **Do not change Crownline's rules to solve the bot's cycle pathology.** The behavior is an AI-policy problem in the measured cases.
2. **Do not promote the board-weight or Crownline-pressure evaluator experiments.** They are useful negative/partial evidence but either displaced cycles or traded away too much playing strength.
3. **Retain the 50-point exact-history repeat penalty as the leading anti-cycle policy candidate.** It is small, explicit, reversible, and materially improved symmetric self-play completion without a measured paired strength loss.
4. **Do not put it into the browser yet.** The next product candidate should combine this trajectory policy with the Stage 2 iterative-deepening + structural-TT search architecture and then be tested as one coherent opponent configuration.

## Next Stage 3 question

Cycle handling and strategic evaluation should now be separated.

The repeat-aware policy answers a trajectory question: *have I already produced this exact state?* It does not teach the engine broader Crownline strategy.

The next evaluator experiment should return to a genuinely strategic omission, introduced independently. Strong candidates include:

- promotion / King utility beyond current square score;
- capture-quota and final-response pressure;
- Game-2 set-outcome context;
- cooldown/readiness and unretired-line access with a more outcome-grounded formulation than the rejected broad line-pressure term.

Whichever is chosen next should use the repeat-aware policy only as a separately switchable control so that strategic strength and cycle suppression remain attributable to different mechanisms.
