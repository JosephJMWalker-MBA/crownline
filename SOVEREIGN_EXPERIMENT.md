# Crownline — Sovereign King Experiment

**Status:** experimental only. This document does not amend `RULES.md`.

## Current refined rule

Human play refined the original Sovereign interpretation after simulation and initial implementation.

> **Sovereign King:** if at least one King has an available capture, the player may decline the mandatory-capture obligation for that turn and make any otherwise legal non-capturing move with any of their pieces. If captures are available only to ordinary pieces, capture remains mandatory. If a King chooses to capture, the existing multiple-jump continuation rule still applies.

The King that could capture does **not** have to be the piece that moves after refusal.

## Evidence boundary

The simulation results below were produced under the **earlier interpretation**:

> when any capture was available, a King could decline and make an otherwise legal one-square King move.

Those results remain useful historical evidence about adding King agency, but they are **not direct evidence for the refined whole-turn release rule**. The refined rule has a larger branching effect and must be evaluated through new human play and, if useful, a fresh simulation pass.

## Why test it

The candidate gives promotion a second meaning beyond backward mobility:

- a normal piece is subject to the board's forced-capture obligation;
- a King can, when it itself has a capture, release the turn from that obligation;
- the player can then redirect the turn toward another legal non-capturing move;
- the existing double capture value of a King remains the liability balancing that additional agency.

The experiment asks whether that added agency enriches Crownline without damaging the capture clock, meld structure, set balance, or game length.

---

## Primary paired-set sample — original King-step interpretation

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

Under the original Sovereign random-play implementation, a position in which a King had an available non-capturing alternative while some capture existed occurred **4.13 times per game** on average. Random players used the refusal option **71.8%** of those opportunities.

### Important nuance on promotion

The original Sovereign implementation increased the **number of promotions per game** by about 31%, while the percentage of games containing at least one promotion was nearly unchanged. The interpretation is not simply “more games reach promotion.” Rather, longer Sovereign games create more room for multiple pieces to promote within games that already contain promotion.

The nearly doubled King-capture rate also matters: greater King agency did not make Kings simply safer. It kept Kings active longer and exposed more doubled capture value to later tactical play.

---

## Small strategy-aware pilot — original King-step interpretation

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

### Supported by the original experiment

1. **Sovereign materially changes play.** It is not flavor text.
2. **The 15-point capture clock survived the original interpretation.** Quota endings remained about 98% in the primary random sample.
3. **Promotion became more consequential.** Kings remained in strategically meaningful positions longer and more pieces could reach promotion during long games.
4. **The liability still bit.** King captures almost doubled under random play, so doubled capture value remained relevant.
5. **Meld activity rose modestly.** Extra King agency appeared to create somewhat more room for Crownline construction.

### Cautions for the refined rule

1. **The refined rule branches more widely.** Refusal can now unlock non-capturing moves by other pieces, not only King steps.
2. **The original random games were already ~36% longer.** A fresh check of pacing and repetition is warranted.
3. **A small repetition/stall signal already existed.** Whole-turn release could strengthen or weaken that signal; it cannot be assumed either way.
4. **Set balance is not yet proven.** The old sample does not validate the refined semantics.
5. **The effect is strategy-sensitive.** Human play is especially important because the value of redirecting the turn depends on positional intent.

---

## Current recommendation

**Do not amend Official Rules v1.0 yet.**

The refined Sovereign rule is now part of the frozen **Crownline v1.1 Candidate** because human play exposed the King-only movement restriction as strategically artificial. That clarification should now be tested directly.

The key human-play question is whether releasing the **turn**—rather than merely releasing the King—creates meaningful positional judgment without making tactical consequences too easy to evade.

Until the promotion gate is satisfied, `RULES.md` remains the authority and Kings remain subject to the v1.0 mandatory-capture rule in Official play.