# Crownline Play Record v1

The browser can export the gameplay observed during the current server session as a JSON play record.

This is deliberately an analysis artifact, not a new game rule and not a replacement for CLSN.

## Why it exists

Human playtests contain information that self-play does not. In particular, a human may discover long-horizon plans, geometry reuse, denial ideas, or King structures that the current evaluator does not represent.

A useful learning record therefore needs more than a move list. Every move stores the exact canonical position before and after the action so later tools can reconstruct the decision under the authoritative v1.1 rules engine.

The core relationship is:

```text
before CLSN
    + chosen action
    + controller / participant
    + optional AI search evidence
    -> after CLSN
```

Because `before_clsn` is reversible, a later analysis tool can regenerate the complete legal action set rather than trusting a stale exported list of alternatives.

## Schema

Top-level fields:

- `schema`: `crownline.play-record`
- `schema_version`: currently `1`
- `sets`: browser-session sequence of competitive sets, including resets and tied-set continuations
- `summary`: added at export time with set/game/move counts and current aggregate state

Each set records:

- sequence within the browser server session
- Crownline set index and rules mode
- Game-1 first-White participant mapping
- carry scores, if this is an agreed continuation set
- how the set was opened and closed
- one or two game records
- aggregate result when completed

Each game records:

- game number and participant/color mapping
- canonical initial CLSN and SHA-256 fingerprint
- ordered move events
- final result and final CLSN when the game completes

Each move event records:

- move index and engine ply before/after
- participant and color
- `controller`: `human` or `computer`
- move notation and selected Crownline/meld line, if any
- canonical CLSN and fingerprint before and after the move
- capture delta
- piece IDs promoted on the move
- Crownlines scored on the move, including Royal status
- quota/final-response state after the move
- score snapshot after the move
- AI profile/search evidence for computer moves

## Intended research use

The first use should be **diagnostic comparison**, not blind imitation training.

For each human decision we can:

1. parse `before_clsn`;
2. regenerate all legal Crownline actions;
3. score the human move and the current AI choice under controlled search;
4. identify systematic features associated with expert-human deviations;
5. test one evaluator hypothesis at a time on frozen human positions;
6. only promote a feature if it improves independent benchmark evidence.

That preserves the same experimental discipline used for the existing Crownline AI work while allowing human-discovered strategy to become a source of reproducible positions.

## Browser behavior

`Export play record` downloads a formatted JSON file. The in-memory record accumulates play across resets for as long as `serve_crownline.py` keeps running, so resetting the board does not discard already recorded moves. Restarting the Python server starts a new recording session.
