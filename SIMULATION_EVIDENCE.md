# Crownline v1.0 — Simulation Evidence

This document records the experimental evidence that informed the Official Rules v1.0.

It is **not** part of the normative rules. `RULES.md` defines how Crownline is played; this file records why several unusual rules were selected.

The simulations used the deterministic Python prototype plus experimental harnesses. Strategy bots were intentionally simple heuristics rather than claims of optimal play. Results should therefore be treated as design evidence, not proof of game-theoretic balance.

Across the successful harnesses used during v0.1 → v1.0 development, approximately **69,500 simulated game instances** were completed.

---

## 1. v0.1 Random Baseline

20,000 random-play games were run against the original single-game dark-square rules.

Key results:

- White wins: **48.9%**
- Black wins: **50.1%**
- Draws: **1.0%**
- Mean length: **32.8 plies**
- Quota-triggered endings: **97.5%**
- Immobilization endings: **2.5%**
- Games with at least one promotion: **78.4%**
- Games ending with at least one scoring Crownline: approximately **0.6%**

Interpretation:

- The basic movement/capture engine produced finite games without pathological loops.
- The 15-point Capture Quota functioned as the dominant game clock.
- The original end-state Crownline scoring rule was effectively dormant.

---

## 2. Capture Quota Sweep

Crown-aware self-play was tested at several quota values.

| Capture Quota | Avg. Plies | Quota Ending | Immobilization | Crownline Ever Formed | Meld Present at End |
|---:|---:|---:|---:|---:|---:|
| 10 | 15.7 | 100.0% | 0.0% | 19.9% | 7.4% |
| **15** | **30.7** | **95.7%** | **3.5%** | **27.9%** | **1.8%** |
| 18 | 40.3 | 70.7% | 27.4% | 29.9% | 1.9% |
| 21 | 47.9 | 19.3% | 78.2% | 34.7% | 1.4% |
| 24 | 53.7 | 8.7% | 86.8% | 34.9% | 1.7% |
| 30 | 52.9 | 0.2% | 96.1% | 34.4% | 1.6% |

Interpretation:

- Quotas below 15 compressed the game severely.
- Quotas above 15 increasingly converted Crownline from a quota-driven game into an immobilization-driven game.
- **15 was retained** because it sat in a useful region where games were long enough to develop but the Capture Bank remained the primary endgame trigger.

---

## 3. Why Crownline Melds Bank Immediately

The original v0.1 rule awarded a Crownline only if the three-piece line still existed at final scoring.

This caused a mismatch:

- Crown-aware players could form Crownlines during play;
- checker movement frequently destroyed those lines before the game ended;
- therefore the Rummy layer rarely affected final score.

Experimental comparisons showed:

- old geometry + end-state melds: meld scored in about **3.2%** of Crown-aware games;
- old geometry + banked melds: about **27.2%**;
- symmetric experimental geometry + banked melds: about **67.0%**.

A 5,000-game random sanity test on the combined candidate produced:

- Crownline ever formed: **19.9%**;
- meld scored: **19.9%**.

Interpretation:

A completed Crownline needed to behave like a Rummy meld: once successfully assembled, the accomplishment should remain banked even if the pieces later move or are captured.

This produced the v1.0 rule:

> Form an eligible Crownline → bank +15 immediately → mark the three participating piece identities meld-used.

---

## 4. Piece-Identity Constraint

Each player has six uniquely numbered pieces, 1 through 6.

A banked Crownline consumes the **meld eligibility**, but not the physical use, of the three participating identities.

This prevents a player from repeatedly farming the same three pieces through multiple Crownlines while allowing those pieces to continue participating in movement, captures, promotion, and Board Value.

A second meld remains theoretically legal using the other three identities.

Observed frequency was very low:

| Capture Quota | Any Meld | Two-Meld Game |
|---:|---:|---:|
| 15 | 67.7% | 0.0% |
| 18 | 75.0% | 0.7% |
| 21 | 74.3% | 2.3% |
| 24 | 69.7% | 1.7% |
| 30 | 73.0% | 2.0% |

Interpretation:

The rules do not need to force two melds to occur. At quota 15, one meld is a normal strategic accomplishment; a second meld can remain a rare feat.

---

## 5. The Single-Game Geometry Problem

The original dark-square Crownline layout showed a strong strategic seat/color effect under simple Crown-aware heuristics.

One experiment produced approximately:

- White: **27.9%**
- Black: **69.8%**

When the Crownline geometry was rotated 180 degrees, the advantage substantially followed the geometry:

- White: **56.2%**
- Black: **40.8%**

This indicated that the apparent imbalance was not adequately described as a generic first-player effect; the physical placement of Crownline nodes mattered.

A separate dual-center symmetric geometry experiment reduced the imbalance, but required ten physical scoring squares to represent nine logical nodes.

The dual-center approach was not adopted into v1.0 because the two-game set solution preserved ordinary checkerboard geometry more cleanly.

---

## 6. Why Crownline Is a Two-Game Set

The final balancing proposal was:

### Game 1

- dark squares;
- normal Lo Shu Crown values;
- one player receives White/first move.

### Game 2

- light squares;
- mirrored geometry;
- players swap sides and first move;
- Crown values are complemented by `10 - v`.

The complete competitive result is the aggregate score across both games.

### Paired-Set Harness

#### Random policy — 4,000 sets / 8,000 games

- Player A set wins: **48.55%**
- Player B set wins: **49.92%**
- Draws: **1.52%**
- Mean aggregate margin A − B: **+0.03 points**

#### Crown-aware policy — 1,000 sets / 2,000 games

- Player A set wins: **48.10%**
- Player B set wins: **50.10%**
- Draws: **1.80%**
- Mean aggregate margin A − B: **+0.76 points**

Interpretation:

Individual games remained structurally asymmetric, but the two-game set made each player experience both conditions and substantially canceled the seat effect at the aggregate level.

The simulation therefore supported defining the **Crownline Set**, rather than a single game, as the official competitive unit.

---

## 7. Why Game 2 Uses Complementary Values

Game 2 uses:

```text
v₂ = 10 - v₁
```

For any Game 1 Crownline:

```text
a + b + c = 15
```

therefore:

```text
(10-a) + (10-b) + (10-c)
= 30 - 15
= 15
```

So the complementary board remains a valid 15-magic-square system.

Ablation testing suggested that swapping sides over a complete set did most of the fairness work. However, complementary scoring did not harm balance and showed a preliminary tendency toward tighter Crown-aware set margins.

Crown-aware ablation sample:

| Game 2 Scoring | A Wins | B Wins | Mean Absolute Set Margin |
|---|---:|---:|---:|
| same values | 50.2% | 46.8% | 19.71 |
| **opposite `10-v`** | **48.4%** | **49.8%** | **18.36** |

The sample is too small to claim optimality, but the complementary rule preserves the core mathematical identity of 15 and provides a coherent second-game inversion.

---

## 8. Set-Level Comebacks

In the paired-set harness, the player who lost Game 1 still won the complete set in approximately:

- **24.2%** of random-policy sets;
- **26.8%** of Crown-aware sets.

Interpretation:

Aggregate scoring keeps Game 1 margin strategically relevant even when a player is unlikely to win that individual game. Game 2 is not ceremonial; it creates meaningful comeback and score-preservation incentives.

---

## 9. Why Ties Remain Ties

The two-game structure exists specifically to make both players experience complementary board conditions.

A one-game sudden-death tiebreaker would reintroduce the asymmetry that the set structure was designed to neutralize.

Therefore v1.0 treats equal aggregate scores as a valid draw.

Players may mutually agree to continue with another **complete two-game set**, preserving both-condition fairness and adding subsequent scores to the tied aggregate total.

---

## 10. What the Simulations Do Not Prove

These experiments do **not** establish:

- solved-game status;
- Nash equilibrium play;
- perfect first-player neutrality;
- optimal square values;
- optimal piece starting order;
- optimal capture rules;
- tournament-level balance under expert humans.

The heuristic policies were deliberately simple. Their purpose was to expose obvious failure modes, compare rule variants under repeatable conditions, and identify rules that caused intended mechanics to appear in actual play.

Human playtesting and stronger search agents remain necessary validation steps.

---

## 11. v1.0 Evidence Standard

Official Rules v1.0 are the frozen experimental baseline.

Future rule changes should answer three questions:

1. **What observed problem does the change address?**
2. **What measurable prediction does the proposed rule make?**
3. **Does simulation and/or human playtesting outperform the v1.0 baseline on that prediction without damaging another core mechanic?**

This keeps Crownline's evolution evidence-driven rather than preference-driven.
