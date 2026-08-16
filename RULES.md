# Crownline — Official Rules v1.0

Crownline is a two-game abstract strategy set combining checker movement and captures, tic-tac-toe geometry, Rummy-style melds, and mathematical scoring.

The official competitive unit is the **Crownline Set**, not a single game.

---

## 1. Objective

Players score through three systems:

1. **Capture Bank** — value earned by capturing opposing pieces.
2. **Board Value** — value of the squares occupied by surviving pieces when a game ends.
3. **Crownline Melds** — permanent 15-point bonuses earned by occupying valid three-node Crownlines with eligible pieces.

A game does **not** end when a Crownline is formed.

A game normally enters its final turn when one player's Capture Bank reaches the **15-point Capture Quota**. The opponent receives one final response turn, then the game is scored.

A Crownline Set contains two games played under complementary board conditions. The two game scores are added together. Highest aggregate score wins the set.

---

## 2. Equipment

Crownline uses:

- one standard **8×8 checkerboard**;
- six numbered pieces for each player, labeled **1, 2, 3, 4, 5, 6**.

Each player's six printed numbers are unique within that player's set of pieces.

The printed number serves as the piece's capture value and persistent identity.

---

## 3. The Crownline Set

A complete Crownline Set consists of **Game 1** and **Game 2**.

Before Game 1, use any mutually accepted random method to determine which player receives White and the first move.

For Game 2:

- the players swap colors/sides;
- the player who moved second in Game 1 moves first in Game 2;
- play moves from the dark squares to the light squares;
- the Crownline grid is mirrored onto the light squares;
- Crownline square values are complemented using `10 - v`.

All game state resets between Game 1 and Game 2, including:

- piece positions;
- captured pieces;
- king status;
- Capture Banks;
- meld eligibility;
- banked melds.

Only the **game scores** carry forward into the set total.

---

## 4. Set Scoring

For player `p`:

```text
SetScore_p = Game1Score_p + Game2Score_p
```

The player with the higher aggregate score after both games wins the Crownline Set.

A single game may be played for teaching, testing, or casual play, but an official competitive Crownline result is determined by the complete two-game set.

---

# GAME RULES

## 5. Playable Squares

### Game 1

Only the **dark squares** are playable.

### Game 2

Only the **light squares** are playable.

Pieces may never occupy or move through the other color of square during that game.

---

## 6. Ordinary Square Values

Every playable non-Crownline square has a Board Value based on its rank:

- ranks 1 and 8: **1 point**;
- ranks 2 and 7: **2 points**;
- ranks 3 and 6: **3 points**;
- ranks 4 and 5: **4 points**.

These ordinary square values are the same in both games.

Crownline squares override the ordinary value of the physical square they occupy.

---

## 7. Game 1 — Crownline Grid

Game 1 uses the following Lo Shu magic-square values:

| | | |
|---|---|---|
| **8 — b6** | **1 — d6** | **6 — f6** |
| **3 — c5** | **5 — e5** | **7 — g5** |
| **4 — b4** | **9 — d4** | **2 — f4** |

Every row, column, and diagonal totals **15**.

The eight Game 1 Crownlines are:

- b6–d6–f6
- c5–e5–g5
- b4–d4–f4
- b6–c5–b4
- d6–e5–d4
- f6–g5–f4
- b6–e5–f4
- f6–e5–b4

---

## 8. Game 2 — Complementary Crownline Grid

Game 2 mirrors the Game 1 Crownline geometry onto the light squares and complements each Crown value:

```text
v₂ = 10 - v₁
```

The logical magic square is therefore:

| | | |
|---|---|---|
| **2 — g6** | **9 — e6** | **4 — c6** |
| **7 — f5** | **5 — d5** | **3 — b5** |
| **6 — g4** | **1 — e4** | **8 — c4** |

Every row, column, and diagonal still totals **15** because:

```text
(10-a) + (10-b) + (10-c) = 30 - (a+b+c)
```

and every original Crownline satisfies:

```text
a + b + c = 15
```

so every complementary Crownline also satisfies:

```text
30 - 15 = 15
```

The eight Game 2 Crownlines are:

- g6–e6–c6
- f5–d5–b5
- g4–e4–c4
- g6–f5–g4
- e6–d5–e4
- c6–b5–c4
- g6–d5–c4
- c6–d5–g4

---

## 9. Starting Pieces — Game 1

### White

- a1 — piece 1
- c1 — piece 2
- e1 — piece 3
- g1 — piece 4
- b2 — piece 5
- d2 — piece 6

### Black

- h8 — piece 1
- f8 — piece 2
- d8 — piece 3
- b8 — piece 4
- g7 — piece 5
- e7 — piece 6

White moves toward rank 8. Black moves toward rank 1.

---

## 10. Starting Pieces — Game 2

Game 2 mirrors the starting geometry onto the light squares.

### White

- h1 — piece 1
- f1 — piece 2
- d1 — piece 3
- b1 — piece 4
- g2 — piece 5
- e2 — piece 6

### Black

- a8 — piece 1
- c8 — piece 2
- e8 — piece 3
- g8 — piece 4
- b7 — piece 5
- d7 — piece 6

White again moves toward rank 8. Black moves toward rank 1.

Because players swap colors between games, each player experiences both starting conditions during a complete set.

---

## 11. Normal Movement

A normal piece moves one playable square diagonally forward into an empty square.

- White moves toward increasing ranks.
- Black moves toward decreasing ranks.

A king may move one playable square diagonally forward or backward.

---

## 12. Captures

A piece captures by jumping diagonally over an adjacent opposing piece into the empty playable square immediately beyond it.

The jumped piece is removed from the board.

For v1.0:

- ordinary pieces capture **forward only**;
- kings capture forward or backward.

### Mandatory Capture

If any legal capture exists, the player **must capture**.

A non-capturing move is illegal while a capture is available.

If multiple legal capture routes exist, the player chooses among them.

### Multiple Captures

If the capturing piece can legally capture again after landing, it must continue jumping during the same turn.

If multiple continuation captures are available, the player chooses the route.

The entire jump sequence counts as one turn.

---

## 13. Capture Bank

When an opposing piece is captured, the capturing player permanently adds that piece's capture value to their Capture Bank for the current game.

A normal piece is worth its printed value.

Examples:

- capturing piece `1` earns 1 Capture Point;
- capturing piece `4` earns 4 Capture Points;
- capturing piece `6` earns 6 Capture Points.

---

## 14. Kings

A normal piece becomes a king when it reaches the opponent's home rank.

- White crowns on rank 8.
- Black crowns on rank 1.

A king may move and capture diagonally forward or backward.

If a normal piece reaches the king row during a multiple-capture sequence, it crowns and its turn immediately ends.

### King Capture Value

A king is worth **double its printed value when captured**.

Examples:

- piece `2` as a king is worth 4 Capture Points;
- piece `4` as a king is worth 8 Capture Points;
- piece `6` as a king is worth 12 Capture Points.

The printed number remains the piece's identity after promotion.

King status does not alter the piece's Crownline eligibility or Board Value.

---

## 15. Crownlines as Rummy-Style Melds

A player forms a Crownline when three of that player's pieces simultaneously occupy all three physical squares of one valid Crownline.

To score the Crownline, all three pieces must still be **meld-eligible**.

When a valid eligible Crownline is formed:

1. the player immediately banks a **15-point Meld Bonus**;
2. the three participating printed piece identities become **meld-used** for the remainder of that game;
3. the pieces remain on the board and continue moving, capturing, promoting, and being captured normally;
4. the banked 15 points can never be lost, even if the Crownline later disappears or one of its pieces is captured.

A meld-used piece may never contribute to another Crownline Meld during that game.

King status does not prevent an otherwise eligible piece from participating in a Crownline Meld.

Because each player has six uniquely identified pieces, a player can theoretically score at most **two Crownline Melds** in one game.

A second meld is legal but is not required for ordinary successful play.

---

## 16. Capture Quota and Final Response Turn

The Capture Quota is:

# 15 Capture Points

When a player's completed turn leaves their Capture Bank at **15 or more**, that player becomes the **Triggering Player**.

The opponent receives exactly **one final response turn**.

After that final response turn, the game ends and Final Game Scoring occurs.

Reaching the quota does **not** automatically win the game.

If the quota is crossed during a multiple-capture sequence, the player must complete the full legal capture sequence before the quota trigger takes effect. All captured value from that sequence is banked.

---

## 17. Immobilization

If the player whose turn it is has:

- no surviving pieces; or
- no legal move,

the game ends immediately and proceeds to Final Game Scoring.

Immobilization is not an automatic checkers-style loss.

The higher mathematical score wins the game.

---

## 18. Final Game Scoring

For player `p`:

```text
GameScore_p = CaptureBank_p + BoardValue_p + MeldBonus_p
```

where:

- `CaptureBank_p` is the accumulated capture value earned during the game;
- `BoardValue_p` is the sum of the values of all squares occupied by that player's surviving pieces when the game ends;
- `MeldBonus_p` is 15 multiplied by the number of Crownline Melds that player banked during the game.

Formally:

```text
S_p = C_p + B_p + 15M_p
```

King status does not multiply Board Value.

Banked Crownline Melds remain part of the score even if the pieces that created them have moved or been captured.

---

## 19. Formal Turn Sequence

Each turn proceeds in this order:

1. Determine whether the current player has any legal move.
2. If not, end the game and score immediately.
3. Determine whether any capture exists.
4. If a capture exists, only capture moves are legal.
5. Perform the chosen move or complete mandatory jump sequence.
6. Remove all captured pieces.
7. Add captured values to the moving player's Capture Bank.
8. Crown the moving piece when applicable.
9. Update board occupation.
10. If the new position forms an eligible Crownline, immediately bank the 15-point Meld Bonus and mark its three piece identities meld-used.
11. If this turn was the opponent's final response turn, end the game and score.
12. Otherwise, if the moving player's Capture Bank has reached 15 for the first time, mark that player as the Triggering Player and grant the opponent exactly one final response turn.
13. Switch players.

---

# SET RESOLUTION

## 20. Winning a Game

After Final Game Scoring:

- the player with the higher Game Score wins that individual game;
- equal Game Scores produce a tied individual game.

Individual game wins are informational only. They do not determine the Crownline Set winner.

The aggregate points do.

---

## 21. Winning the Crownline Set

After Game 2:

```text
SetScore_A = Game1Score_A + Game2Score_A
SetScore_B = Game1Score_B + Game2Score_B
```

- higher aggregate Set Score wins;
- equal aggregate Set Scores produce an official draw.

A player may therefore lose Game 1 and still win the set by preserving enough points and outperforming the opponent in Game 2.

---

## 22. Tied Sets

A tied Crownline Set is a valid final result.

The rules do not manufacture an artificial winner after mathematical equality.

After a tied set, the players may mutually choose either to:

1. **accept the draw**; or
2. **play another complete Crownline Set**.

If both players agree to continue:

- another full two-game set is played;
- a new random assignment determines White/first move for the new Game 1;
- the players again swap colors and first move for Game 2;
- the previously tied aggregate score remains in force;
- scores from the additional set are added to the existing aggregate total.

There is no one-game sudden death in the official rules.

Any continuation used to resolve a tie must preserve the complete two-game set structure.

For tournament or organized play, the tie-continuation policy may be declared before competition begins. If no continuation policy exists, a tied aggregate score is recorded as a draw.

---

## 23. Strategic Structure

A Crownline move can affect several economies at once:

1. **Mobility** — where pieces can move next.
2. **Material** — which numbered pieces survive.
3. **Position** — the value and geometry of occupied squares.
4. **Meld structure** — whether three eligible identities can form a Crownline.
5. **Clock** — how close either player is to triggering the 15-point endgame.
6. **Set margin** — how many points carry into the complementary second game.

A locally valuable move is therefore not necessarily a strategically superior move.

---

## 24. Rules Version

This document defines **Crownline Official Rules v1.0**.

The v1.0 rules are considered frozen as the baseline ruleset for implementation and playtesting.

Future changes should be versioned explicitly and evaluated against this baseline rather than silently replacing it.
