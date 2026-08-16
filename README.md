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

Crownline is played as two games.

### Game 1

- play on the dark squares;
- use the normal Lo Shu Crown values;
- a random method determines who moves first.

### Game 2

- play on the light squares using the mirrored geometry;
- players swap sides and first move;
- Crown values are complemented using:

```text
v₂ = 10 - v₁
```

So the Game 2 magic square becomes:

```text
2 9 4
7 5 3
6 1 8
```

Every Crownline still totals **15**.

Each game resets pieces, captures, kings, and meld eligibility. The scores do not reset.

```text
Set Score = Game 1 Score + Game 2 Score
```

The player with the higher aggregate score wins the set.

## Ties

If the aggregate scores are equal after Game 2, the official result is a **draw**.

The players may mutually agree to play another complete two-game Crownline Set. If they continue, aggregate scoring continues from the tied total until a later complete set produces a leader.

There is no single-game sudden-death tiebreaker in the base rules.

## Repository status

The repository currently contains:

- `RULES.md` — **Official Rules v1.0**
- `SIMULATION_EVIDENCE.md` — experimental evidence behind the v1.0 rule choices
- `crownline.py` — preserved **v0.1** deterministic engine
- `play_crownline.py` — v0.1 console player
- `test_crownline.py` — v0.1 engine tests

> **Implementation note:** the rules have advanced to v1.0, while the Python engine is intentionally preserved at v0.1. The next implementation milestone is to bring the engine into conformance with the frozen v1.0 specification rather than silently rewriting the prototype history.

## Design evidence

Crownline's rules were refined through simulation rather than intuition alone.

The experimental work tested random play, heuristic strategy bots, capture quotas, Crownline persistence, board asymmetry, banked melds, complementary scoring, and two-game set balance. The evidence is recorded separately so that future rule changes can be compared against the current baseline instead of replacing its rationale.

See [`SIMULATION_EVIDENCE.md`](SIMULATION_EVIDENCE.md) for details.

## Rules

The normative specification is [`RULES.md`](RULES.md).

If this README and the official rules ever differ, **`RULES.md` governs**.

---

**Status:** Rules v1.0 frozen; v1.0 engine implementation pending.
