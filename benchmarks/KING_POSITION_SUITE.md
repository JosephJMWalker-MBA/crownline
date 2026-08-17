# King-rich hard-case position suite

`king-v0.1` is a frozen root/evaluator guardrail for Crownline v1.1 (`candidate`) AI research.

It exists because the original 16-position frozen suite is intentionally early/midgame-biased and contains **no Kings**. That suite remains useful for detecting broad policy disruption, but it cannot tell us whether a King-specific evaluator feature changes late-game decisions sensibly.

## Source

The twelve fixtures in `king_position_suite_v0_1.json` are exact canonical CLSN states sampled from repetition diagnostics produced by measured 150 ms p50/p200 trajectories. Every fixture therefore comes from a position the current search/evaluator family actually reached rather than from a hand-authored hypothetical.

The suite preserves per-fixture provenance:

- workflow run;
- artifact ID;
- benchmark configuration name;
- source scenario ID;
- observed exact-cycle length;
- canonical CLSN and SHA-256 fingerprint.

The current selection covers both Game-1 and Game-2 geometries, two through six Kings on the board, already-banked ordinary and Royal Crownlines, and exact repetition cycles of 4, 8, and 20 plies.

## What it is for

Use this suite to answer questions such as:

- Does a proposed King/promotion evaluator feature activate on real late-game states?
- How many frozen late-game root actions change under a candidate weight?
- Does the same feature behave differently when Crownlines have already retired?
- Does a proposed static feature merely move a known cycle decision or alter late-game policy broadly?

The loader `crownline_king_position_suite.py` rejects noncanonical CLSN, fingerprint drift, terminal fixtures, positions without Kings, missing provenance, duplicate positions, loss of Game-1/Game-2 coverage, or loss of the 4/8/20-ply cycle-shape coverage.

## What it is not for

The twelve fixtures are **independent hard cases**, not naturally paired Game-1/Game-2 scenarios. Do not feed them into the ordinary paired-set benchmark and interpret the result as a competitive win-rate measurement.

Full-trajectory and seat-balanced strength claims should continue to use the canonical paired position suite/harness. The King-rich suite is the late-game equivalent of a regression corpus: it tells us whether a strategic feature changes decisions on relevant states before we spend a full trajectory run or consider product inclusion.

## Current first use

The first King-utility diagnostic confirmed that every proposed King feature family has meaningful variation on `king-v0.1`, while all King-feature margins are identically zero on the original 16-position suite. This validates the reason for keeping both guardrails:

```text
early paired suite      -> broad/early policy stability
King hard-case suite    -> late-game King-specific policy stability
full trajectory harness -> completion, repetition, and paired outcome evidence
```

Neither suite changes Crownline's rules, and neither is part of the browser runtime.
