# Stage 2 Conclusion — Search Engineering

Stage 2 asked a constrained question under Crownline v1.1 (`candidate`):

> **How much stronger search can Crownline buy from better search engineering while leaving the evaluator and game rules unchanged?**

The experiments were deliberately semantics-preserving. A candidate search optimization only earned credit when completed searches continued to choose the same action as fixed-depth Baseline A on the frozen 16-position CLSN1 suite.

## What Stage 2 established

### Exact structural transposition caching earns its place

A canonical CLSN1 string remains the external state representation and benchmark boundary. Inside search, however, a cheaper structural tuple can represent the same future-relevant game facts without repeatedly serializing text.

The structural exact transposition table stores only fully searched exact values. Alpha-beta cutoff bounds are not mislabeled as exact values. This implementation preserved Baseline A policy on the frozen suite while reducing repeated search work.

At fixed depth 4, structural transposition caching was already a wall-clock improvement over ordinary Baseline A. Under iterative deepening it continued to reduce work consistently.

### Move ordering is mathematically useful but not yet computationally profitable

Static and score-based ordering substantially improved alpha-beta pruning. The strongest combined experiments reduced depth-4 expansions from 16,685 baseline nodes to 7,203 nodes, a reduction of about 56.8 percent, while preserving the same chosen actions.

In the current Python implementation, however, the work needed to construct, estimate, and sort child states consumed the pruning benefit. Delta-equivalent estimates and carried score state narrowed the overhead, but further micro-optimization of that same ordering family stopped producing meaningful gains.

Stage 2 therefore does **not** promote move ordering into the product engine yet.

## Iterative deepening changes the product question

Fixed depth is the wrong final control surface for an interactive opponent. The iterative engine now searches depth 1 → 2 → 3 → 4 under a monotonic wall-clock budget and returns only the deepest **fully completed** iteration. An unfinished iteration is discarded rather than allowed to leak a partial answer into play.

Across the frozen 16-position suite, every completed iterative iteration matched the corresponding fixed-depth Baseline A action and search-node count.

The baseline time-budget profile on the CI runner was:

| Budget | Completed-depth distribution | Mean completed depth |
| --- | --- | ---: |
| 50 ms | 14×d2, 1×d3, 1×d4 | 2.19 |
| 150 ms | 15×d3, 1×d4 | 3.06 |
| 500 ms | 2×d3, 14×d4 | 3.88 |
| 1000 ms | 16×d4 | 4.00 |

This makes approximately **150 ms** the first measured budget that delivers depth 3 essentially everywhere on the frozen suite. Approximately **500 ms** delivers depth 4 on nearly every tested position without requiring a fixed half-second delay when a position finishes earlier.

## Structural TT under the same time budget

The final Stage 2 experiment paired ordinary iterative deepening against iterative deepening with the structural exact TT, alternating execution order across positions to reduce systematic run-order bias.

Every completed TT iteration remained action-equivalent to fixed-depth Baseline A. The TT engine was **never shallower** than baseline in the paired run.

| Budget | Baseline mean depth | Structural-TT mean depth | TT deeper / same / shallower | Baseline d4 | TT d4 |
| --- | ---: | ---: | --- | ---: | ---: |
| 50 ms | 2.19 | 2.19 | 0 / 16 / 0 | 1 | 1 |
| 150 ms | 3.06 | 3.06 | 0 / 16 / 0 | 1 | 1 |
| 500 ms | 3.88 | 3.94 | 1 / 15 / 0 | 14 | 15 |
| 1000 ms | 4.00 | 4.00 | 0 / 16 / 0 | 16 | 16 |

At 500 ms the structural TT converted one additional position—`standard-start` Game 2—from a completed depth 3 to a completed depth 4. At 1000 ms both engines hit the current depth-4 ceiling, but the TT engine still finished about 4.2 percent faster on average and expanded about 25.2 percent fewer nodes.

The small depth uplift at the current cap should not be exaggerated. The important result is that exact search reuse consistently reduces work without changing policy, and occasionally converts that saved work into a deeper completed search when a position lies near a budget boundary.

## Stage 2 decision

The strongest search architecture currently supported by evidence is:

```text
canonical CLSN1 position boundary
        ↓
iterative deepening under a soft wall-clock budget
        ↓
CLSN-equivalent structural exact transposition table
        ↓
unchanged Baseline A evaluator and deterministic tie-breaking
        ↓
deepest fully completed action
```

This architecture is a **benchmark/product candidate**, not yet the browser default.

If responsiveness is the primary product constraint, the 150 ms region is the strongest measured starting point because it produces depth 3 on 15 of 16 frozen positions. If additional search depth is worth a more deliberate opponent response, the 500 ms region produces depth 4 on 15 of 16 positions with the structural TT.

No evidence from Stage 2 justifies a fixed depth-4 browser bot, and no search-engineering result solves the known reversible-cycle pathology. The next stage should therefore stop asking only how to search the current evaluator faster and begin asking what Crownline-specific strategic information the evaluator is missing.

## Stage 3 boundary

Stage 3 should improve **decision quality while keeping the Stage 2 search architecture available as a controlled computational substrate**.

The first evaluator experiments should focus on the clearest empirical failure already observed: reversible four-ply cycles despite available exits. Candidate features should be introduced one at a time and tested against Baseline A on the same frozen CLSN suite plus the known repetition-producing trajectories.

Potential hypotheses include progress-sensitive evaluation, Crownline construction/denial pressure, promotion/King utility, quota/final-response risk, and explicit cycle-escape preference. These should remain separable features rather than being collapsed immediately into one opaque heuristic.

The browser opponent remains unchanged until a candidate earns promotion through this evidence path.

## Evidence

- `STAGE1_DEPTH_CONCLUSION.md`
- `iterative_time_budget_v0_1_summary.json`
- `iterative_tt_time_budget_v0_1_summary.json`
- `delta_ordering_plus_tt_v0_1_summary.json`
- `carried_ordering_v0_1_summary.json`
- `position_suite_v0_1.json`
