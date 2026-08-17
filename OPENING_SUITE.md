# Crownline Opening Suite v0.1

Crownline's AI benchmarks are deterministic. Replaying the exact same initial position many times therefore reproduces the same trajectory rather than creating independent evidence.

Opening Suite v0.1 introduces a small set of **distinct, reproducible Crownline v1.1 starting trajectories** so search changes can be compared across more than one exact opening condition.

## Rules boundary

The suite targets **Crownline v1.1 Candidate** (`rules_mode="candidate"`) exclusively.

That is the bot-development game: whole-turn Sovereign refusal, King-gated Crownlines, three-turn Crownline cooldowns, per-player line retirement, Royal +30, the 15-point capture quota/final-response rule, complementary Game 1/Game 2 geometry, and complete two-game set scoring all remain authoritative.

Older v1.0, Sovereign-only, and Crowned-only profiles remain useful controls but do not define the AI target.

## Why fixed opening prefixes

A useful engine comparison needs more than repeated self-play from one exact deterministic state, but the suite should not be handpicked to favor one engine.

v0.1 therefore uses **AI-independent legal-action quantile prefixes**:

1. start from the authoritative standard Game 1 position under v1.1;
2. enumerate every legal move + Crownline-choice action in stable lexical order;
3. select an action by a frozen quantile between 0 and 1;
4. apply the move through the authoritative rules engine;
5. repeat for the scenario's opening prefix;
6. hand the resulting CrownlineSet to the engines under test.

The bot's evaluator, search depth, tie-breaking, and preferred move are never consulted while constructing an opening.

This is not meant to imitate a human opening book. It is an experimental-design device for creating distinct, auditable starting trajectories without cherry-picking positions based on which bot wins them.

## Seat balance

Each scenario is run twice:

- Participant A is White in Game 1 of the first set;
- Participant B is White in Game 1 of the second set.

The scripted prefix is defined at the color/game-state level, so both legs reach the same canonical board state before engine decisions begin. Only participant identity changes.

After the prefix, the set proceeds normally. If the scenario begins partway through Game 1, that game finishes from the opening state and Game 2 begins from the normal complementary starting position.

## v0.1 scenarios

The initial suite contains eight scenarios:

| Scenario | Opening plies | Purpose |
| --- | ---: | --- |
| `standard-start` | 0 | untouched control |
| `low-lattice` | 8 | lower legal-action quantiles |
| `high-lattice` | 8 | higher legal-action quantiles |
| `median-line` | 8 | repeated median action |
| `quarter-cross-a` | 8 | mixed lower/upper quartiles |
| `quarter-cross-b` | 8 | complementary mixed rhythm |
| `full-spread` | 8 | extremes, quartiles, and median |
| `weave` | 8 | second mixed selector path |

The harness asserts that all eight produce distinct canonical state fingerprints and that participant seat assignment does not change the resulting opening state.

## What v0.1 does and does not claim

The suite gives us **eight distinct deterministic conditions**. It does not magically make those conditions a statistically representative sample of all Crownline positions.

The initial scenarios emphasize early development because they are generated from short legal prefixes. Later suite versions should deliberately add validated positions that exercise distinctive v1.1 mechanics, including:

- promotion and King transitions;
- Sovereign capture-refusal choices;
- Crownline construction and denial;
- active cooldown states;
- retired-line scarcity;
- quota/final-response pressure;
- Game 2 positions with meaningful aggregate-set context.

Those later scenarios should have explicit provenance and canonical fingerprints rather than being invented ad hoc to make a particular engine look stronger.

## Benchmark command

Depth 2 versus depth 3 across the full suite:

```bash
python3 crownline_opening_benchmark.py \
  --suite v0.1 \
  --depth-a 2 \
  --depth-b 3 \
  --repetition-limit 3 \
  --json benchmarks/opening_v0_1_d2_vs_d3.json
```

This attempts 16 sets: two seat-balanced sets for each of eight scenarios.

Exact-state repetition remains a diagnostic stop, not a Crownline draw rule. Any scenario pair with an incomplete set is retained as evidence but excluded from scenario-pair win/loss claims.

## Evidence standard

The strongest claim from this stage is not "depth 3 is X% better at Crownline." The defensible question is narrower:

> Across the frozen v0.1 scenario suite, how often does depth 3 outperform depth 2, how often does either engine repeat, and what additional search cost buys the observed difference?

Opening Suite v0.1 is a measurement scaffold. It should expand only when a new scenario category adds information that the current suite does not already provide.
