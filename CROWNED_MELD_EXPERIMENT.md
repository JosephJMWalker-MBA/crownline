# Crownline — Crowned Meld Experiment

**Status:** experimental only. This document does not amend `RULES.md`.

## Candidate rule

The Crowned Meld profile now tests five linked ideas:

1. a scoring Crownline must contain **at least one King**;
2. a normal Crownline scores **+15**;
3. three Kings forming a Crownline create a **Royal Crownline worth +30**;
4. the three participating piece identities receive a **3-turn Crownline cooldown** rather than becoming permanently spent;
5. once a player scores a particular Crownline geometry, that line is **retired for that player for the rest of the game**.

Cooldown affects only meld eligibility. Pieces continue to move, capture, promote, and be captured normally.

A standing line never scores merely because its cooldown expires. After cooldown, the same pieces may score again only by newly completing a **different Crownline that the player has not already retired**.

Line retirement is per player, not global. If White retires the center row, Black may still score that same geometry later.

---

## Why test it

Human play exposed several tensions in Official v1.0 and the first Crowned Meld prototype:

- strategically difficult late-game Crownlines could fail to score because one participating identity had been used much earlier;
- early access to the Crown grid could matter before promotion, even though the game's title and strongest visual identity center on crowning;
- permanent identity exhaustion made legitimate late-game accomplishments feel invisible;
- cooldown-only reuse created a repeatable position in which the strategically best cycle was to wait out the designation and farm the same Crownline again.

The revised proposal separates two jobs:

- **piece cooldown controls tempo** — the same pieces cannot chain new scoring formations immediately;
- **line retirement controls repetition** — a player cannot turn one stable geometry into a renewable +15 loop.

The intended rhythm becomes:

```text
promote → create Crownline → score → cooldown → reposition → find another available line
```

---

## Simulation signal before implementation

A broad simulation comparison found that requiring a King substantially delayed Crownline scoring while leaving the 15-point capture clock largely intact.

In random paired-set play, the 3-turn cooldown did **not materially lengthen games** relative to the existing rules. The major behavioral change came from the King prerequisite: melds became later and rarer.

A deliberate Crownline-seeking stress test found that reuse was possible but uncommon:

- games with a meld: about **5.7%** under Official movement with the King-required cooldown branch;
- games with 2+ melds: about **1.4%**;
- games where the same three identities later scored again: about **0.75%**;
- games where the same geometric line later scored again: about **0.83%**.

Under the more mobile Sovereign environment, repeat scoring remained limited:

- games with a meld: about **13.4%**;
- games with 2+ melds: about **3.1%**;
- same-three reuse: about **1.4%**;
- same-line rescoring: about **1.6%**.

Those aggregate frequencies made cooldown-only reuse look tolerable, but human play found a local position where repetition was actually the best strategy and same-line farming became obvious. That playtest evidence motivated the additional retirement rule.

### Royal frequency

Three-King lines were exceptionally rare in the sampled games. In one paired same-seed ablation, **5 Royal Crownlines appeared among 79 total meld events across 5,000 candidate games**. Moving those events from +15 to +30 had negligible aggregate effect in that sample.

That makes +30 a plausible playtest reward for a genuinely exceptional board accomplishment, not yet a proven final value.

---

## Current implementation

The browser exposes **Experimental · Crowned Meld** as a third rules profile alongside Official v1.0 and Experimental Sovereign.

When a Crownline scores in this profile:

- the authoritative Python engine records its point value and whether it was Royal;
- the three participating identities receive cooldown `3`;
- only that player's subsequent turns reduce the countdown;
- the board label shows the remaining designation as a superscript: `³`, `²`, `¹`;
- the scored Crownline geometry is retired for that player;
- after the third subsequent turn completes, the pieces become eligible again;
- those pieces may later score a different unretired Crownline;
- a Royal Crownline receives explicit +30 feedback.

The browser now also exposes a per-player eight-line **Crownline Map** so retirement is visible rather than hidden bookkeeping.

The Python engine provides authoritative reasons when a newly completed visible line does not score, including:

- no King in the formation;
- one or more pieces still on cooldown;
- the line was already retired by that player.

Official v1.0 remains unchanged.

---

## Human-play questions

The next evidence should come from actual play rather than only larger random simulations:

1. Does requiring a King make Crownline formation feel earned rather than merely rare?
2. Is three turns long enough to prevent trivial chaining between different lines?
3. Is the superscript designation intuitive during live play?
4. Does Royal +30 feel proportionate to the difficulty of placing three Kings in a valid line?
5. Does retiring each geometry once per player create interesting route planning through the eight possible Crownlines?
6. Do players begin defending **remaining available lines**, rather than merely defending the current formation?
7. Does the profile reduce the perceived early positional advantage without making the Crownline layer disappear?

Until those questions are answered, this profile remains experimental and `RULES.md` remains the normative specification.
