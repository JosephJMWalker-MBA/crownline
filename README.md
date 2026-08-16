# Crownline

**Crownline** is a two-game abstract strategy set that combines checker movement and captures, tic-tac-toe geometry, Rummy-style melds, and mathematical scoring.

The official competitive unit is not a single game. It is a **Crownline Set**: two games played under complementary board conditions, with scores added together.

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

The runtime exposes three clearly separated profiles:

- **Official v1.0** — the normative rules in `RULES.md`; Kings remain subject to mandatory capture and meld-used piece identities remain permanently spent for scoring within that game.
- **Experimental Sovereign** — a King may decline the mandatory-capture obligation and make an otherwise legal one-square King move. Ordinary pieces remain capture-bound, and a King that chooses to capture must still complete its legal multiple-jump sequence.
- **Experimental Crowned Meld** — a scoring Crownline must contain at least one King. A normal Crownline scores **+15**. Three Kings create a **Royal Crownline worth +30**. After scoring, all three participating pieces receive a **3-turn Crownline cooldown**. Each of the eight Crownline geometries may score **once per player per game**; the line is then retired for that player, while the opponent may still score the same geometry. Once cooldown clears, the same pieces may score again only by newly completing a different unretired Crownline.

Changing the rules profile starts a fresh Crownline Set. Ordinary **Reset set** preserves the currently selected profile.

The experimental profiles do **not** amend Official Rules v1.0. See [`SOVEREIGN_EXPERIMENT.md`](SOVEREIGN_EXPERIMENT.md) and [`CROWNED_MELD_EXPERIMENT.md`](CROWNED_MELD_EXPERIMENT.md).

## Repository structure

- `RULES.md` — **Official Rules v1.0**
- `SIMULATION_EVIDENCE.md` — evidence behind the v1.0 rule choices
- `SOVEREIGN_EXPERIMENT.md` — evidence for the opt-in Sovereign King experiment
- `CROWNED_MELD_EXPERIMENT.md` — rationale and evidence for King-required reusable melds and per-player line retirement
- `crownline_rules.py` — Game 1 / Game 2 geometry, scoring values, and explicit rules-profile identifiers
- `crownline_game.py` — deterministic single-game movement, capture, promotion, meld, cooldown, retirement, diagnostics, quota, scoring, and profile-aware move generation
- `crownline_set.py` — two-game set state, color swap, aggregate scoring, tied-set continuation, and rules-profile persistence
- `crownline_ai.py` — lightweight deterministic computer opponent search
- `crownline.py` — stable public Python API
- `play_crownline.py` — console player for a complete Crownline Set
- `test_crownline.py` — Official v1.0 conformance tests
- `test_rules_profiles.py` — Official/Sovereign profile-boundary tests
- `test_crowned_meld.py` — Crowned Meld, Royal, cooldown, retirement, and diagnostic tests
- `serve_crownline.py` — dependency-free local browser/API server
- `web/` — Three.js/WebGL playable client, onboarding, help, and contextual rule feedback

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
- choose **Official v1.0**, **Experimental · Sovereign King**, or **Experimental · Crowned Meld** from the Rules menu;
- changing the Rules profile starts a fresh set so rules never mutate mid-game;
- in Crowned Meld mode, a piece on cooldown shows a superscript countdown such as `5³ → 5² → 5¹ → 5`;
- Crowned Meld also displays a per-player **Crownline Map** showing all eight geometries as available (`○`) or retired (`✓`);
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
- choose **Computer · Player B** from the opponent menu for single-player mode.

The current computer opponent uses a deterministic depth-2 minimax-style search over authoritative Python game state. It is intended as a playable baseline opponent, not as a claim of solved or optimal Crownline play.

## Meld-choice edge case

A single move can theoretically complete more than one eligible Crownline. The engine exposes the competing lines and requires the player to choose which one to bank rather than silently selecting for them.

## Design evidence

Crownline's rules were refined through simulation and human play rather than intuition alone. Experimental work has tested random play, heuristic strategy bots, capture quotas, Crownline persistence, board asymmetry, banked melds, complementary scoring, two-game set balance, Sovereign King behavior, King-required melds, Royal scoring, three-turn meld cooldowns, and human-discovered same-line farming.

See [`SIMULATION_EVIDENCE.md`](SIMULATION_EVIDENCE.md), [`SOVEREIGN_EXPERIMENT.md`](SOVEREIGN_EXPERIMENT.md), and [`CROWNED_MELD_EXPERIMENT.md`](CROWNED_MELD_EXPERIMENT.md) for details.

## Rules authority

The normative specification is [`RULES.md`](RULES.md).

If this README, an experiment, or the browser differs from the official rules, **`RULES.md` governs Official v1.0**.

---

**Status:** Official Rules v1.0 frozen; v1 Python engine implemented; WebGL board directly playable; baseline computer opponent implemented; Sovereign King and Crowned Meld available as explicitly experimental local rules profiles; first-launch/profile onboarding and engine-backed rule diagnostics implemented.
