# Crownline

**Crownline** is a two-game abstract strategy set that combines checker movement and captures, tic-tac-toe geometry, Rummy-style melds, and mathematical scoring.

The official competitive unit is not a single game. It is a **Crownline Set**: two games played under complementary board conditions, with scores added together.

## Current implementation boundary

Crownline is both a playable game implementation and an evidence-driven rules/AI research environment.

- **Official Rules v1.0** remain the normative rules in [`RULES.md`](RULES.md).
- The browser currently launches into the **Experimental Crownline v1.1 Candidate** for active playtesting. That launch default does not promote v1.1 to official status.
- The v1.1 candidate remains **feature-frozen** under a play → observe → record discipline. Promotion requires an explicit review decision after additional complete two-game sets.
- The browser exposes both the original **Baseline A** computer opponent and a separately selectable **Research / Strong** opponent for v1.1 human product playtesting.
- Experimental AI features are promoted only when they pass their stated measurement gates. Rejected hypotheses and negative results are preserved as research evidence rather than silently folded into the product opponent.

## Core idea

Each player begins with six uniquely numbered pieces: **1, 2, 3, 4, 5, 6**.

Pieces move and capture using checker-style rules. Captures are mandatory when available, multiple jumps continue within the same turn, and pieces can be crowned as kings.

At the same time, nine scoring nodes form a hidden 3×3 **Crownline grid** based on the Lo Shu magic square:

```text
8 1 6
3 5 7
4 9 2
```

Every row, column, and diagonal totals **15**.

Under Official v1.0, occupying three Crownline nodes in a valid line with three eligible piece identities creates a meld worth **15 points**. The meld is banked immediately; the pieces remain in play, but those piece identities cannot be reused in another Official v1.0 meld.

## Why 15 matters

The number 15 connects the game's two scoring systems:

- every valid Crownline totals **15**;
- the capture quota is **15 points**;
- each normal banked Crownline is worth **15 points**.

Once a player finishes a turn with at least 15 capture points, the opponent receives one final response turn and the game is scored.

## Scoring a game

A player's game score is:

```text
Game Score = Capture Bank + Board Value + Meld Bonus
```

- **Capture Bank** — value of captured enemy pieces; captured kings are worth double their printed value.
- **Board Value** — value of the squares occupied by surviving pieces at game end.
- **Meld Bonus** — banked Crownline points earned during play.

There is no instant three-in-a-row victory.

## The Crownline Set

### Game 1

- play on the dark squares;
- use the normal Lo Shu Crown values;
- a random method determines who moves first.

### Game 2

- play on the light squares using mirrored geometry;
- players swap sides and first move;
- Crown values are complemented using `v₂ = 10 - v₁`.

The Game 2 logical magic square is:

```text
2 9 4
7 5 3
6 1 8
```

Every Crownline still totals **15**.

Each game resets pieces, captures, kings, and meld eligibility. Only game scores carry into the set total.

```text
Set Score = Game 1 Score + Game 2 Score
```

## Ties

If aggregate scores are equal after Game 2, the official result is a **draw**.

Players may mutually agree to another complete two-game set. If they continue, the previously tied aggregate score remains in force. There is no single-game sudden-death tiebreaker in the base rules.

## Rules profiles

The runtime exposes four separated profiles:

- **Experimental Crownline v1.1 Candidate** — the leading playtest profile. It combines refined Sovereign Kings with Crowned Meld scoring: if a King has an available capture, the player may decline capture for the turn and make any otherwise legal non-capturing move with any piece; if only ordinary pieces can capture, mandatory capture still applies. A Crownline requires at least one King; normal Crownlines score **+15**; three Kings score **Royal +30**; scoring pieces receive a 3-turn Crownline cooldown; and each Crownline geometry may score once per player per game before retiring for that player. **This candidate remains feature-frozen for play → observe → record testing.**
- **Official v1.0** — the normative rules in `RULES.md`; Kings remain subject to mandatory capture and meld-used piece identities remain permanently spent for scoring within that game.
- **Experimental Sovereign** — isolates the refined King-agency experiment. If a King has an available capture, the player may decline capture for the turn and make any otherwise legal non-capturing move with any piece. If captures are available only to ordinary pieces, mandatory capture still applies. A King that chooses to capture must complete its legal multiple-jump sequence.
- **Experimental Crowned Meld** — isolates the scoring experiment. A scoring Crownline must contain at least one King, uses the 3-turn cooldown, Royal +30, and per-player line retirement, while Kings remain subject to mandatory capture.

Changing the rules profile starts a fresh Crownline Set. Ordinary **Reset set** preserves the currently selected profile.

The browser's current launch default is the **v1.1 Candidate** because it is the active human-play profile. That presentation choice does **not** change rules authority: the v1.1 candidate and comparison profiles do not amend Official Rules v1.0.

See [`V1_1_CANDIDATE.md`](V1_1_CANDIDATE.md), [`V1_1_PLAYTEST_LOG.md`](V1_1_PLAYTEST_LOG.md), [`SOVEREIGN_EXPERIMENT.md`](SOVEREIGN_EXPERIMENT.md), and [`CROWNED_MELD_EXPERIMENT.md`](CROWNED_MELD_EXPERIMENT.md).

## Candidate playtest phase

The current rules-design mode is intentionally conservative:

```text
play → observe → record
```

The v1.1 candidate should not receive new mechanics unless actual play exposes a repeatable exploit, severe pacing problem, unintuitive scoring outcome, or a rule that consistently forces strategically nonsensical play.

A play-observed ambiguity in the first Sovereign wording has already been corrected: declining a King capture now releases the **whole turn** rather than forcing the King itself to make the replacement move. That refinement is part of the frozen candidate and should be tested directly.

If several additional complete two-game sets continue to produce varied, coherent play without a recurring structural problem, the agreed promotion path is:

1. promote the frozen candidate to **Official Crownline v1.1**;
2. make v1.1 the default polished gameplay experience;
3. move Official v1.0, Sovereign-only, and Crowned-Meld-only into a clearly labeled **Legacy & Experimental Rules** area;
4. preserve all older profiles for provenance and regression testing.

Promotion requires an explicit review decision; it is not automatic.

## Repository structure

- `RULES.md` — **Official Rules v1.0**
- `V1_1_CANDIDATE.md` — frozen combined Sovereign + Crowned Meld candidate and promotion gate
- `V1_1_PLAYTEST_LOG.md` — human-play evidence log for the frozen candidate
- `SIMULATION_EVIDENCE.md` — evidence behind the v1.0 rule choices
- `SOVEREIGN_EXPERIMENT.md` — historical Sovereign simulation plus the refined whole-turn rule boundary
- `CROWNED_MELD_EXPERIMENT.md` — rationale and evidence for King-required reusable melds and per-player line retirement
- `AI_BENCHMARKING.md` — reproducible computer-opponent measurement protocol
- `benchmarks/` — auditable AI experiment results, preserved failures, and current research conclusions
- `crownline_rules.py` — Game 1 / Game 2 geometry, scoring values, and explicit rules-profile identifiers
- `crownline_game.py` — deterministic single-game movement, capture, promotion, meld, cooldown, retirement, diagnostics, quota, scoring, and profile-aware move generation
- `crownline_set.py` — two-game set state, color swap, aggregate scoring, tied-set continuation, and rules-profile persistence
- `crownline_ai.py` — deterministic Baseline A computer opponent
- `crownline_maturity_product_candidate.py` — measured Research / Strong opponent architecture used for v1.1 human playtesting
- `crownline.py` — stable public Python API
- `play_crownline.py` — console player for a complete Crownline Set
- `test_crownline.py` — Official v1.0 conformance tests
- `test_rules_profiles.py` — Official/Sovereign profile-boundary tests
- `test_crowned_meld.py` — Crowned Meld, Royal, cooldown, retirement, and diagnostic tests
- `test_v1_1_candidate.py` — combined-profile and experiment-isolation tests
- `serve_crownline.py` — dependency-free local browser/API server
- `web/` — Three.js/WebGL playable client, onboarding, help, Crownline-map hover previews, contextual rule feedback, and AI-profile selection

## Run the tests

```bash
pytest -q
```

## Play in the console

```bash
python3 play_crownline.py
```

## Run the browser prototype

On macOS, use:

```bash
python3 serve_crownline.py
```

Then open:

```text
http://127.0.0.1:8765
```

The browser is intentionally non-authoritative: it renders serialized Python state and submits attempted moves back to the Python engine. Legal moves, captures, melds, cooldowns, retired lines, scoring, diagnostics, game transitions, set resolution, rules-profile behavior, and computer-opponent moves remain server-side.

### Browser interaction and onboarding

- first launch presents a short five-step tutorial covering sets, movement, scoring, the Crown Grid, and the Game 1 → Game 2 relationship;
- each Rules profile has its own first-time tutorial, and the active profile can be re-explained from **? Help** at any time;
- the persistent Help panel covers Basics, Scoring, Crownlines, and the Current Rules profile;
- choose **Experimental · Crownline v1.1 Candidate**, **Official v1.0**, **Experimental · Sovereign King**, or **Experimental · Crowned Meld** from the Rules menu;
- changing the Rules profile starts a fresh set so rules never mutate mid-game;
- in Crowned Meld and v1.1 Candidate modes, a piece on cooldown shows a superscript countdown such as `5³ → 5² → 5¹ → 5`;
- those modes also display a per-player **Crownline Map** showing all eight geometries as available (`○`) or retired (`✓`);
- hover or keyboard-focus any Crownline Map entry to illuminate that exact row, column, or diagonal on the 3D board;
- if a newly completed visible line does not score, the Python engine supplies the exact reason, such as **King required**, **piece cooldown**, or **line already retired**;
- every square displays algebraic notation (`a1` through `h8`);
- click one of the current player's movable pieces;
- legal destination squares are highlighted;
- green markers indicate ordinary destinations;
- amber markers indicate capture destinations;
- click a highlighted destination to submit the move;
- pieces animate along their legal paths and captured pieces visibly leave play;
- completing a Crownline illuminates the scoring nodes and banks its meld value;
- Royal Crownlines receive explicit +30 feedback;
- promotion produces a visual King-crowning cue;
- Game 1 → Game 2 and final-set resolution use explicit transition states rather than abrupt board replacement;
- capture banks, meld counters, and aggregate score cards pulse when their values change;
- drag horizontally to rotate the board, or use **Flip board** for an exact 180° view;
- if multiple legal capture routes reach the same destination, the interface asks which route to use rather than silently choosing;
- the move-notation panel remains available as a fallback/reference;
- choose **Computer · Player B** from the opponent menu for single-player mode;
- under the v1.1 Candidate, choose either **Baseline A** or **Research / Strong** as the computer profile.

### Computer opponents

**Baseline A** is the original deterministic depth-2 minimax-style opponent over authoritative Python game state. It is preserved as a reproducible baseline and remains available across rules profiles.

**Research / Strong** is available only under the v1.1 Candidate. Its current measured composition uses:

```text
150 ms iterative deepening
+ structural exact transposition table
+ p200 exact-history repeat policy
+ promotion maturity w10
+ max depth 4
```

The stronger profile earned advancement to **human product playtesting** after controlled benchmark work and a reversed-role directional confirmation. That is not a claim that Crownline is solved, that the engine is optimal, or that its measured weights are universal constants. Baseline A remains available so product impressions can be compared against a stable reference.

## Meld-choice edge case

A single move can theoretically complete more than one eligible Crownline. The engine exposes the competing lines and requires the player to choose which one to bank rather than silently selecting for them.

## Design and AI research evidence

Crownline's rules were refined through simulation and human play rather than intuition alone. Experimental work has tested random play, heuristic strategy bots, capture quotas, Crownline persistence, board asymmetry, banked melds, complementary scoring, two-game set balance, Sovereign King behavior, King-required melds, Royal scoring, three-turn meld cooldowns, human-discovered same-line farming, and the combined Sovereign + Crowned Meld rules candidate.

The original Sovereign simulations used the earlier King-step-only refusal semantics. Human play later refined that rule to whole-turn release, so the older numbers should not be treated as direct validation of the current candidate semantics.

Computer-opponent research follows the same evidence discipline:

```text
hypothesis → isolated experiment → independent gate → promote or reject → preserve evidence
```

That process has produced both positive and negative results. The current Research / Strong composition earned human-facing integration, while later **unretired King coverage** was rejected for product promotion after it increased Crownline-seeking behavior without demonstrating greater competitive strength. A subsequent **mandatory-capture-only quiescence** hypothesis was also rejected after it failed the frozen human tactical gate; the useful result retained from that study was the tactical blame-horizon method.

Preserving those negative results is intentional. A feature changing observable behavior is not enough to call it a stronger policy.

See [`AI_BENCHMARKING.md`](AI_BENCHMARKING.md), [`benchmarks/README.md`](benchmarks/README.md), [`benchmarks/STAGE3_MATURITY_P200_COMPOSITION_CONCLUSION.md`](benchmarks/STAGE3_MATURITY_P200_COMPOSITION_CONCLUSION.md), [`benchmarks/HUMAN_DECISION_V0_1_CONCLUSION.md`](benchmarks/HUMAN_DECISION_V0_1_CONCLUSION.md), and [`benchmarks/TACTICAL_QUIESCENCE_CONCLUSION.md`](benchmarks/TACTICAL_QUIESCENCE_CONCLUSION.md) for the current evidence chain.

See [`SIMULATION_EVIDENCE.md`](SIMULATION_EVIDENCE.md), [`SOVEREIGN_EXPERIMENT.md`](SOVEREIGN_EXPERIMENT.md), [`CROWNED_MELD_EXPERIMENT.md`](CROWNED_MELD_EXPERIMENT.md), [`V1_1_CANDIDATE.md`](V1_1_CANDIDATE.md), and [`V1_1_PLAYTEST_LOG.md`](V1_1_PLAYTEST_LOG.md) for rules-development evidence.

## Rules authority

The normative specification is [`RULES.md`](RULES.md).

If this README, an experiment, or the browser differs from the official rules, **`RULES.md` governs Official v1.0**. The browser's v1.1 launch default is an active playtest choice, not a change to that authority.

---

**Status:** Official Rules v1.0 frozen; WebGL board directly playable; browser currently launches the feature-frozen v1.1 Candidate for active human playtesting; Baseline A and the measured v1.1-only Research / Strong opponent are both implemented; Sovereign King and Crowned Meld remain comparison controls; onboarding, Crownline geometry hover previews, engine-backed rule diagnostics, reproducible AI benchmarking, human-decision diagnostics, and preserved rejected experiments are implemented; v1.1 promotion remains an explicit future review decision.
