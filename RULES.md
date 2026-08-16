# Crownline — Rules Specification v0.1

## 1. Objective

Crownline combines:

- **Checkers:** movement, captures, kings, forced jumps
- **Tic-tac-toe:** eight three-square Crownlines
- **Rummy:** numbered pieces, melds, a scoring threshold, and endgame accounting

There is **no immediate three-in-a-row victory**.

Players accumulate value through captures and positioning. Once a player reaches the capture quota, the game enters its final turn and is decided by score.

## 2. Board

Crownline uses a standard **8×8 checkerboard**. Only the 32 dark squares are playable.

White begins at the bottom and moves toward rank 8. Black begins at the top and moves toward rank 1.

### Base Square Values

Every playable square has a point value.

Non-Crownline squares are valued according to their distance from the nearest home edge:

- Ranks 1 and 8: **1 point**
- Ranks 2 and 7: **2 points**
- Ranks 3 and 6: **3 points**
- Ranks 4 and 5: **4 points**

The nine Crownline squares override these values.

## 3. Crownline Grid

Nine playable squares form a hidden 3×3 scoring grid using the Lo Shu magic square:

| | | |
|---|---|---|
| **8 — b6** | **1 — d6** | **6 — f6** |
| **3 — c5** | **5 — e5** | **7 — g5** |
| **4 — b4** | **9 — d4** | **2 — f4** |

Every row, column, and diagonal totals **15**.

The eight possible Crownlines are:

- b6–d6–f6
- c5–e5–g5
- b4–d4–f4
- b6–c5–b4
- d6–e5–d4
- f6–g5–f4
- b6–e5–f4
- f6–e5–b4

A Crownline is controlled when one player occupies all three squares simultaneously.

## 4. Complete Board Value Map

| Rank | Playable squares |
|---|---|
| 8 | b8=1, d8=1, f8=1, h8=1 |
| 7 | a7=2, c7=2, e7=2, g7=2 |
| 6 | **b6=8, d6=1, f6=6**, h6=3 |
| 5 | a5=4, **c5=3, e5=5, g5=7** |
| 4 | **b4=4, d4=9, f4=2**, h4=4 |
| 3 | a3=3, c3=3, e3=3, g3=3 |
| 2 | b2=2, d2=2, f2=2, h2=2 |
| 1 | a1=1, c1=1, e1=1, g1=1 |

## 5. Pieces

Each player begins with six numbered checkers: **1, 2, 3, 4, 5, 6**.

The printed number is the piece's **capture value**.

### White Setup

- a1 — 1
- c1 — 2
- e1 — 3
- g1 — 4
- b2 — 5
- d2 — 6

### Black Setup

- h8 — 1
- f8 — 2
- d8 — 3
- b8 — 4
- g7 — 5
- e7 — 6

## 6. Movement

A normal checker moves one playable square diagonally forward into an empty square.

A king may move one square diagonally in either direction.

For v0.1, ordinary pieces also **capture forward only**. Kings capture in either direction.

## 7. Captures

A piece captures by jumping diagonally over an adjacent opposing piece into an empty square immediately beyond it. The captured piece is removed.

### Mandatory Capture

If any legal capture exists, the player **must capture**. A normal move is illegal while a capture is available.

If multiple capture routes exist, the player chooses among them.

### Multiple Captures

If the capturing piece can make another legal capture after landing, it must continue jumping during the same turn. The player chooses the route when multiple continuation captures are available.

The entire capture sequence counts as one turn.

## 8. Capture Bank

When an opposing piece is captured, its printed value is added to the capturing player's **Capture Bank**.

Capture points are permanent once earned.

## 9. Kings

A normal piece becomes a king when it reaches the opponent's home rank.

- White crowns on rank 8.
- Black crowns on rank 1.

A king may move and capture diagonally forward or backward.

If a piece reaches the king row during a multiple-capture sequence, it crowns and its turn immediately ends.

### King Capture Value

A king is worth **double its printed value when captured**.

The printed number itself does not change. King status changes mobility and capture liability only.

## 10. Capture Quota

The Capture Quota is **15 points**.

When a player's completed turn leaves their Capture Bank at 15 or more, the endgame is triggered. That player becomes the **Triggering Player**.

The opponent receives **one final turn**. After that final turn, scoring occurs.

Crossing 15 does **not** automatically win the game.

If the quota is crossed during a multiple-jump sequence, the full legal capture sequence is completed first and all captured values are banked.

## 11. Crownlines as Melds

At final scoring, each completed Crownline acts as a Rummy-style **meld** worth **15 points**.

A single occupied Crownline square may belong to only one scoring meld.

Therefore, overlapping Crownlines cannot both score if they share a piece. The player receives the maximum possible number of pairwise-disjoint completed Crownlines.

## 12. Final Scoring

For player p:

```text
FinalScore = CaptureBank + BoardValue + MeldBonus
```

Where:

- **CaptureBank** = all capture points earned
- **BoardValue** = sum of square values occupied by surviving pieces
- **MeldBonus** = 15 × number of non-overlapping completed Crownlines

King status does not multiply Board Value.

Formally:

```text
S_p = C_p + B_p + 15M_p
```

## 13. Winner

After the final response turn:

- Highest Final Score wins.
- Equal scores produce a draw.

There are no additional v0.1 tiebreakers.

## 14. Immobilization

If the player whose turn it is has no surviving pieces or no legal move, the game ends immediately and proceeds to final scoring.

There is no automatic checkers-style loss. The mathematically superior position wins.

## 15. Formal Turn Sequence

1. Determine whether the current player has any legal moves.
2. If not, end the game and score.
3. Determine whether any capture exists.
4. If a capture exists, only capture moves are legal.
5. Perform the chosen move or complete jump sequence.
6. Remove captured pieces.
7. Add captured piece values to the player's Capture Bank.
8. Crown the moving piece when applicable.
9. Update board occupation and Crownline state.
10. If this was the opponent's final response turn, end the game.
11. Otherwise, if the player's Capture Bank has reached 15 for the first time, mark that player as Triggering Player and give the opponent exactly one final turn.
12. Switch players.

## 16. v0.1 Design Principle

A move may affect four things at once:

1. **Mobility** — where pieces can move
2. **Material** — which pieces survive
3. **Position** — how much occupied territory is worth
4. **Clock** — how close a player is to triggering the 15-point endgame

The intended strategic tension is that improving one category may damage another.

A player may rationally sacrifice a low-value piece, refuse an otherwise attractive capture, abandon a high-value square, force an opponent to capture, promote a valuable piece despite increasing its capture liability, or deliberately push an opponent over the quota while holding the stronger final board.

## 17. Prototype Status

### Locked for v0.1

- 8×8 board
- six pieces per player
- numbered 1–6 pieces
- mandatory captures
- multiple jumps
- kings
- double capture value for kings
- nine Lo Shu Crownline nodes
- 15-point Crownline melds
- 15-point Capture Quota
- one final opponent turn
- final mathematical scoring
- no immediate three-in-a-row victory

### Balance assumptions requiring playtesting

- starting arrangement
- non-Crownline square values
- 15-point capture quota
- king doubling
- 15-point meld bonus
- forward-only captures for ordinary pieces
- whether immobilization should cause scoring or automatic defeat
