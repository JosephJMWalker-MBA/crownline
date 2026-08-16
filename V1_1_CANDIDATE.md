# Crownline v1.1 Candidate

**Status:** frozen experimental promotion candidate. This document does not amend `RULES.md`.

The v1.1 candidate combines the two experimental mechanics that performed best in human play: **Sovereign King movement** and **Crowned Meld scoring**.

## Candidate freeze

As of the current playtest milestone, the candidate rules are **feature-complete and frozen for observation**.

Development mode is now:

```text
play → observe → record
```

not:

```text
invent → adjust → invent
```

No new rule mechanics should be added unless actual play exposes a concrete structural failure, repeatable exploit, severe pacing problem, or unintuitive scoring outcome. Cosmetic, onboarding, accessibility, implementation, testing, and presentation work may continue without reopening the ruleset.

## Candidate rules

All Official v1.0 set structure, board geometry, capture scoring, 15-point capture quota, final-response turn, Game 1 / Game 2 complementarity, aggregate set scoring, and tie handling remain unchanged except where explicitly modified below.

### Sovereign Kings

- Ordinary pieces remain subject to mandatory capture.
- A King may decline a mandatory capture and instead make any otherwise legal one-square King move.
- If a King chooses to capture, it must complete the full legal multi-jump sequence.
- Kings remain worth double their printed value when captured.

### Crowned Melds

A scoring Crownline must:

- be newly completed by the move;
- occupy one of the eight Crownline geometries;
- use three distinct piece identities;
- contain at least one King;
- use three pieces whose Crownline cooldowns are clear; and
- use a Crownline geometry that the scoring player has not already retired in that game.

A normal Crownline scores **+15**.

A Crownline formed by three Kings is a **Royal Crownline** and scores **+30**.

### Three-turn Crown cooldown

After a Crownline scores, all three participating pieces receive cooldown `3`.

- Only that player's subsequent turns reduce the cooldown.
- Cooldown progresses `3 → 2 → 1 → ready`.
- A cooldown piece may still move, capture, defend, promote, and be captured normally.
- Cooldown restricts only Crownline scoring eligibility.
- A standing formation never scores simply because cooldown expires.

### Per-player line retirement

When a player scores a Crownline, that geometric line is retired **for that player for the remainder of that game**.

- The opponent may still score the same geometry.
- Recovered pieces may later score again, but only by newly completing a different Crownline that remains available to that player.
- The same geometric Crownline cannot be farmed repeatedly by cycling out and back in.

## Why combine the experiments

Human play exposed complementary strengths and weaknesses.

Crowned Meld made promotion and King preservation central to the scoring game, but mandatory capture could force the very King required for a planned Crownline away from the position.

Sovereign King gave Kings meaningful agency, but by itself that agency risked functioning mainly as an evasive privilege.

Combined, the mechanics give sovereignty a scoring purpose and make promotion a genuine phase change:

```text
ordinary piece
    ↓
promotion
    ↓
Sovereign King
    ↓
capture / defend / build Crownline / deny Crownline
```

The King gains strategic freedom while remaining a high-value capture target.

## Promotion gate

The candidate should be promoted to **Official Crownline v1.1** only after several additional complete two-game human sets are played under the frozen candidate without discovering a new structural failure.

The exact number of sets is less important than evidence quality. Promotion should require that play continues to feel strategically coherent across different positions rather than merely repeating one favorable game.

A promotion-blocking finding includes any of the following:

- a repeatable exploit;
- a rule that forces obviously inferior or nonsensical play rather than creating a strategic tradeoff;
- a severe pacing or repetition problem;
- Crownline scoring becoming trivial, irrelevant, or excessively dominant;
- a recurring unintuitive scoring outcome that onboarding cannot reasonably solve;
- a meaningful color/seat advantage that survives the two-game set structure.

Minor balance impressions or single unusual positions should be recorded before changing rules.

## Playtest focus

During candidate play, watch especially for:

1. whether Sovereign refusal creates meaningful choices rather than easy escapes;
2. whether King-gated Crownlines occur often enough to remain central to the game;
3. whether the 3-turn cooldown feels strategic rather than administrative;
4. whether per-player line retirement naturally creates planning around the remaining Crownline Map;
5. whether Royal +30 feels proportionate to three-King formation difficulty;
6. whether the 15-point capture clock still produces satisfying game length;
7. whether either color/seat develops a repeatable advantage across the two-game set.

## Promotion implementation plan

If the promotion gate is satisfied:

1. promote this frozen candidate to **Official Crownline v1.1**;
2. update the normative rules specification and conformance tests;
3. make v1.1 the default polished gameplay experience;
4. move **Official v1.0**, **Experimental Sovereign King**, and **Experimental Crowned Meld** into a clearly labeled **Legacy & Experimental Rules** area;
5. preserve all previous rulesets for provenance, comparison, and regression testing rather than deleting them.

No part of that promotion should happen automatically merely because time passes; it requires an explicit promotion decision after playtest review.

## Runtime profile

The browser currently exposes this ruleset as:

**Experimental · Crownline v1.1 Candidate**

The older **Experimental Sovereign King** and **Experimental Crowned Meld** profiles remain available as comparison controls.

Official v1.0 remains the normative specification until the promotion gate is explicitly satisfied.
