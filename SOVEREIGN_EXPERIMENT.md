# Crownline — Sovereign King Experiment

**Status:** experimental only. This document does not amend `RULES.md`.

## Candidate rule

> **Sovereign King:** when any capture is available, all captures remain legal, but a King may decline the mandatory-capture obligation and make an otherwise legal one-square King move. Ordinary pieces remain bound by mandatory capture. If a King chooses to capture, the existing multiple-jump continuation rule still applies.

This is the full-strength interpretation tested here: a King may refuse capture even when that King itself has a capture available.

## Why test it

The candidate gives promotion a second meaning beyond backward mobility:

- a normal piece is subject to the board's forced-capture obligation;
- a King gains the ability to refuse that obligation;
- the existing double capture value of a King remains the liability balancing that additional agency.

The experiment asks whether that added agency enriches Crownline without damaging the capture clock, meld structure, set balance, or game length.

---

## Primary paired-set sample

The primary comparison used **500 random two-game sets per ruleset**. Game 1 / Game 2 pairing, complementary scoring, and all other Official Rules v1.0 remained unchanged. A 250-ply experimental ceiling was used only to detect pathological cycles; v1.0 itself does not contain this ceiling.

| Metric | v1.0 | Sovereign | Change |
|---|---:|---:|---:|
| Completed sets | 500 / 500 | 498 / 500 | 2 Sovereign sets hit experimental cap |
| Player A set wins | 48.2% | 51.8% | +3.6 pp |
| Player B set wins | 50.2% | 46.2% | -4.0 pp |
| Draws | 1.6% | 2.0% | +0.4 pp |
| Mean A−B set margin | -0.17 | +1.97 | +2.15 points |
| Mean absolute set margin | 23.52 | 20.13 | -14.4% |
| Average plies / game | 33.31 | 45.27 | **+35.9%** |
| Captures / game | 5.86 | 6.20 | +5.8% |
| Capture points / game | 24.04 | 26.29 | +9.3% |
| Promotions / game | 1.45 | 1.90 | **+31.2%** |
| Games with ≥1 promotion | 78.9% | 77.4% | -1.5 pp |
| King captures / game | 0.265 | 0.505 | **+90.4%** |
| Melds / game | 0.129 | 0.168 | +30.4% |
| Games with a meld | 12.5% | 16.3% | +3.8 pp |
| Quota-triggered endings | 98.1% | 97.9% | essentially unchanged |
| Immobilization endings | 1.9% | 1.9% | unchanged |
| Ply-cap games | 0.0% | 0.2% | small cycle/stall signal |

Under Sovereign random play, a position in which a King had an available non-capturing alternative while some capture existed occurred **4.13 times per game** on average. Random players used the refusal option **71.8%** of those opportunities.

### Important nuance on promotion

Sovereign increased the **number of promotions per game** by about 31%, while the percentage of games containing at least one promotion was nearly unchanged. The interpretation is not simply “more games reach promotion.” Rather, longer Sovereign games create more room for multiple pieces to promote within games that already contain promotion.

The nearly doubled King-capture rate also matters: greater King agency did not make Kings simply safer. It kept Kings active longer and exposed more doubled capture value to later tactical play.

---

## Small strategy-aware pilot

A smaller **75-set-per-ruleset heuristic pilot** was also run. The heuristic prioritized immediate capture value, square value, promotion, Crownline potential, and meld completion. It was intentionally lightweight and is not an optimal-play engine.

In that pilot, Sovereign changed aggregate metrics much less:

- average game length: 33.19 → 33.49 plies;
- captures/game: 5.92 → 5.93;
- capture points/game: 25.21 → 25.14;
- promotions/game: 0.913 → 0.905;
- meld games: 36.9% → 38.5%;
- quota endings: 96.0% → 95.9%.

The heuristic encountered a usable Sovereign refusal opportunity **1.16 times/game** and declined capture on **33.9%** of those opportunities, far less often than random play.

Both heuristic variants showed a small number of long-cycle capped games, so this pilot is directional rather than conclusive.

---

## Interpretation

### Supported

1. **Sovereign materially changes play.** It is not flavor text.
2. **The 15-point capture clock survives.** Quota endings remained about 98% in the primary random sample.
3. **Promotion becomes more consequential.** Kings remain in strategically meaningful positions longer and more pieces can reach promotion during long games.
4. **The liability still bites.** King captures almost doubled under random play, so doubled capture value remains relevant.
5. **Meld activity rises modestly.** Extra King agency appears to create somewhat more room for Crownline construction.

### Cautions

1. **Random games became ~36% longer.** That is too large to treat as a free improvement.
2. **A small repetition/stall signal appeared.** Two of 500 random Sovereign sets reached the experimental 250-ply ceiling; none of the v1.0 random sets did.
3. **Branching increases.** A Sovereign King adds legal non-capture moves precisely in positions where standard checkers logic would have narrowed the move set to captures. This increases both player choice and computer-search cost.
4. **Set balance is not yet proven.** The 500-set sample did not show an obvious catastrophic imbalance, but the A/B shift is large enough to justify a larger sample before adoption.
5. **The effect is strategy-sensitive.** The heuristic used Sovereign refusal far less often than random play and showed much smaller changes to game length and capture behavior.

---

## Current recommendation

**Do not amend Official Rules v1.0 yet.**

Sovereign is promising enough to keep, but the experiment says it deserves human playtesting and a larger strategy-aware simulation rather than immediate promotion to v1.1.

The key human-play question is not merely whether Sovereign feels powerful. It is whether the refusal decision creates meaningful positional judgment without producing avoidable repetition or making already-won games take too long.

Until that is established, `RULES.md` remains the authority and Kings remain subject to the v1.0 mandatory-capture rule.
