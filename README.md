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

Occupying three Crownline nodes in a valid line with three eligible piece identities creates a **meld** worth **15 points**. The meld is banked immediately; the pieces remain in play, but those piece identities cannot be reused in another meld.

## Why 15 matters

The number 15 connects the game's two scoring systems:

- every valid Crownline totals **15**;
- the capture quota is **15 points**;
- each banked Crownline meld is worth **15 points**.

Once a player finishes a turn with at least 15 capture points, the opponent receives one final response turn and the game is scored.

## Scoring a game

A player's game score is:

```text
Game Score = Capture Bank + Board Value + 15 × Banked Melds
```

- **Capture Bank** — value of captured enemy pieces; captured kings are worth double their printed value.
- **Board Value** — value of the squares occupied by surviving pieces at game end.
- **Banked Melds** — completed Crownlines already claimed during play.

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

## Repository structure

- `RULES.md` — **Official Rules v1.0**
- `SIMULATION_EVIDENCE.md` — evidence behind the v1.0 rule choices
- `crownline_rules.py` — Game 1 / Game 2 geometry, scoring values, and immutable rule variants
- `crownline_game.py` — deterministic single-game movement, capture, promotion, meld, quota, and scoring engine
- `crownline_set.py` — two-game set state, color swap, aggregate scoring, and tied-set continuation
- `crownline_ai.py` — lightweight deterministic computer opponent search
- `crownline.py` — stable public Python API
- `play_crownline.py` — console player for a complete Crownline Set
- `test_crownline.py` — v1 conformance tests
- `serve_crownline.py` — dependency-free local browser/API server
- `web/` — Three.js/WebGL playable client

## Run the tests

```bash
pytest -q test_crownline.py
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

The browser is intentionally non-authoritative: it renders serialized Python state and submits attempted moves back to the Python engine. Legal moves, captures, melds, scoring, game transitions, set resolution, and computer-opponent moves remain server-side.

### Browser interaction

- every square displays algebraic notation (`a1` through `h8`);
- click one of the current player's movable pieces;
- legal destination squares are highlighted;
- green markers indicate ordinary destinations;
- amber markers indicate capture destinations;
- click a highlighted destination to submit the move;
- pieces animate along their legal paths and captured pieces visibly leave play;
- completing a Crownline illuminates the three scoring nodes and surfaces the `+15` banked meld;
- promotion produces a visual King-crowning cue;
- Game 1 → Game 2 and final-set resolution use explicit transition states rather than abrupt board replacement;
- capture banks, meld counters, and aggregate score cards pulse when their values change;
- drag horizontally to rotate the board, or use **Flip board** for an exact 180° view;
- if multiple legal capture routes reach the same destination, the interface asks which route to use rather than silently choosing;
- the move-notation panel remains available as a fallback/reference;
- choose **Computer · Player B** from the opponent menu for single-player mode.

The current computer opponent uses a deterministic depth-2 minimax-style search over authoritative Python game state. It is intended as a playable baseline opponent, not as a claim of solved or optimal Crownline play.

## Meld-choice edge case

A single move can theoretically complete more than one eligible Crownline through the moved piece. Because that piece identity cannot belong to two melds, the v1 engine exposes the competing Crownlines and requires the player to choose which one to bank rather than silently selecting for them.

## Design evidence

Crownline's rules were refined through simulation rather than intuition alone. The experimental work tested random play, heuristic strategy bots, capture quotas, Crownline persistence, board asymmetry, banked melds, complementary scoring, and two-game set balance.

See [`SIMULATION_EVIDENCE.md`](SIMULATION_EVIDENCE.md) for details.

## Rules authority

The normative specification is [`RULES.md`](RULES.md).

If this README and the official rules differ, **`RULES.md` governs**.

---

**Status:** Official Rules v1.0 frozen; v1 Python engine implemented; WebGL board directly playable with animated move/scoring feedback; baseline computer opponent implemented.
