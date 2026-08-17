# Crownline AI Benchmarking Protocol

Crownline's computer opponent should improve by evidence, not by stacking several changes together and deciding that the result "feels stronger."

This protocol establishes the current opponent as a reproducible baseline and defines the measurement boundary for future search and evaluation work.

## Baseline A

**Baseline A** is the current implementation in `crownline_ai.py`:

- deterministic minimax-style search;
- alpha-beta pruning;
- default browser depth 2;
- authoritative Python game state only;
- evaluation dominated by current mathematical score, with smaller meld-count and mobility terms;
- deterministic lexicographic tie-breaking.

The benchmark milestone does **not** modify that engine. `crownline_benchmark.py` wraps it through an adapter and measures it externally.

The report stores SHA-256 fingerprints for:

- `crownline_ai.py`;
- the authoritative rules engine (`crownline_rules.py`, `crownline_game.py`, `crownline_set.py`);
- the benchmark harness itself.

That makes a saved result auditable even if the repository later evolves.

## Experimental unit

The unit of competition is the same unit defined by Crownline itself: the **complete two-game set**.

A benchmark pair contains two complete sets:

1. Participant A is White in Game 1 of the first set;
2. Participant B is White in Game 1 of the second set.

Each individual set already swaps colors between Game 1 and Game 2. Alternating the Game 1 starting color across the benchmark pair adds another seat-balance control.

The engines remain attached to Participants A and B across both legs. This allows the report to ask whether engine A or engine B is stronger rather than confusing engine identity with color.

## Determinism and seeds

The current baseline engine contains no randomness, so a random seed would be decorative rather than meaningful. Re-running the same engine versions, rules engine, depths, and seat assignment should reproduce the same moves.

Wall-clock timing will still vary with machine load and hardware. Compare latency measurements on the same machine and environment whenever possible.

If a future engine introduces randomness, the benchmark protocol must add and record an explicit seed before that engine can be compared scientifically.

## Search instrumentation

The baseline engine is intentionally left untouched.

For each decision, the harness temporarily wraps the existing private `_search` function and counts invocations. Because the baseline recursively resolves that same module symbol, this counts visited search nodes without changing search logic. The original function is restored immediately after each move.

The report records both:

- **root actions** — legal move + Crownline-choice actions considered at the current position;
- **search nodes** — calls into the existing recursive baseline search beneath the root.

This instrumentation is single-threaded by design.

## Metrics

Every game records:

- final White and Black scores;
- score mapped back to Participants A and B;
- plies;
- capture banks;
- meld counts;
- end reason;
- per-engine decision count;
- total and mean decision time;
- search nodes;
- root actions;
- capture points earned;
- promotions;
- Crownlines scored;
- Sovereign opportunities;
- Sovereign refusals;
- quota triggers;
- final-response moves.

The tournament summary additionally records:

- A/B set wins and draws;
- decisive win rate;
- aggregate score totals;
- mean set margin;
- paired A-minus-B margins;
- mean paired margin;
- end-reason counts;
- mean nodes and milliseconds per decision;
- nodes per second;
- Sovereign refusal rate.

## Sovereign metric definition

A **Sovereign opportunity** is a position where:

- at least one legal capture belongs to a King; and
- at least one legal non-capturing move is also present.

A **Sovereign refusal** occurs when the engine chooses one of those non-capturing alternatives.

This measures actual use of the v1.1 freedom-of-choice rule rather than merely counting Kings on the board.

## Benchmark safety cap

`--max-game-plies` is a benchmark safety boundary, not a Crownline rule.

If a game reaches the cap, its set is marked incomplete and excluded from competitive win-rate calculations. The cap remains in the report as evidence of possible repetition or search-policy pathology.

The default is 300 plies per game.

## Commands

Baseline symmetry/sanity run:

```bash
python3 crownline_benchmark.py \
  --pairs 10 \
  --depth-a 2 \
  --depth-b 2 \
  --json benchmarks/baseline_d2_vs_d2.json
```

First controlled search-depth experiment:

```bash
python3 crownline_benchmark.py \
  --pairs 10 \
  --depth-a 2 \
  --depth-b 3 \
  --json benchmarks/depth2_vs_depth3.json
```

Depth 2 versus depth 4:

```bash
python3 crownline_benchmark.py \
  --pairs 10 \
  --depth-a 2 \
  --depth-b 4 \
  --json benchmarks/depth2_vs_depth4.json
```

The harness defaults to the frozen `candidate` rules profile. Other profiles remain available through `--rules-mode` for control experiments.

## Experimental discipline

Change **one hypothesis at a time**.

Examples:

- depth 2 → depth 3 while evaluation is unchanged;
- add move ordering while depth/evaluation are unchanged;
- add a transposition table while the evaluator remains unchanged;
- add one evaluation feature or one tightly related feature bundle while search remains fixed.

Do not simultaneously change depth, evaluation, move ordering, caching, and pruning and then claim to know why the bot improved.

Strength and efficiency are separate outcomes. A stronger engine that requires 30× the computation may still be useful, but it is a different engineering result from becoming stronger at roughly equal cost.

## Planned progression

### Stage 0 — freeze and measure Baseline A

Run depth-2 self-play and preserve its fingerprints and results.

### Stage 1 — pure depth experiment

Compare depth 2 against depths 3 and 4 with the current evaluator unchanged. This answers how much strength is available from lookahead alone and what it costs in latency/nodes.

### Stage 2 — search engineering

Introduce and isolate:

- move ordering;
- transposition caching;
- iterative deepening;
- later, time-budgeted search.

### Stage 3 — Crownline-specific evaluation

Candidate features include:

- promotion and King value;
- King safety;
- tactical capture exposure and multi-jump risk;
- Crownline threats and denials;
- cooldown readiness;
- retired-line scarcity;
- Sovereign option value;
- quota/final-response timing;
- aggregate two-game set context.

Each feature must earn its place empirically.

### Stage 4 — parameter optimization

Once the feature set is justified, tune weights through automated self-play rather than intuition alone.

### Stage 5 — alternative search/learning approaches

Only after the classical engine has a measured ceiling should Crownline evaluate MCTS, learned value functions, or self-play neural methods.

## Interpretation

A good benchmark result should be expressible as an evidence-backed engineering claim, for example:

> Engine B won 64% of decisive paired sets against Baseline A while searching 22% fewer nodes per decision.

The point is not merely to make the bot harder. The goal is to make improvements **reproducible, attributable, and measurable**.
