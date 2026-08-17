# Crownline State Notation (CLSN1)

Crownline needs a reversible position format before benchmark scenarios can be treated as durable experimental fixtures. `CLSN1` is the canonical notation for a **single Crownline game position**.

The design goal is analogous to FEN in chess: a position should be readable, serializable, restorable, comparable, and shareable without depending on a Python object, move history, browser state, or a particular AI implementation.

## Canonical form

A CLSN1 position is one ASCII line:

```text
CLSN1|g=1|r=candidate|t=W|b=0,0|q=-|o=0|e=-|p=a1:W1,b2:W5,b8:B4,c1:W2,d2:W6,d8:B3,e1:W3,e7:B6,f8:B2,g1:W4,g7:B5,h8:B1|mw=-|mb=-|cw=-|cb=-
```

Fields are emitted in this fixed order:

| Field | Meaning |
| --- | --- |
| `g` | Game geometry: `1` or `2` |
| `r` | Rules profile: `official`, `sovereign`, `crowned`, or `candidate` |
| `t` | Side to move: `W` or `B` |
| `b` | White,Black capture banks |
| `q` | Capture-quota triggering player: `W`, `B`, or `-` |
| `o` | Terminal flag: `0` or `1` |
| `e` | End reason, or `-` |
| `p` | Pieces on the board |
| `mw` | White's banked Crownline melds |
| `mb` | Black's banked Crownline melds |
| `cw` | White Crownline cooldowns |
| `cb` | Black Crownline cooldowns |

## Piece encoding

A board token has the form:

```text
square:owner-id[-king]
```

The actual compact syntax is:

```text
a1:W1
c4:W6K
b3:B4K
```

`K` marks a King. Piece identities remain the printed values `1` through `6`; doubled King capture value is derived from King status and is not stored separately.

Board tokens are sorted by algebraic square in canonical output.

## Meld encoding

A meld token has four parts:

```text
square.square.square:id.id.id:points:royal
```

Example:

```text
g4.e4.c4:3.4.2:15:0
```

A Royal Crownline uses `30:1`. The line must be one of the eight Crownline geometries for the selected game variant. The three identities must be distinct.

For v1.1, banked melds also preserve per-player line retirement because a scored geometric line is retired for that player. Current cooldown state is stored independently in `cw` / `cb`.

## Cooldown encoding

Cooldown entries are `piece_id:own_turns_remaining` and are sorted by identity:

```text
cw=2:3,5:1
```

`-` means no active cooldowns.

## What CLSN1 deliberately does not encode

`CLSN1` is **position notation**, not replay notation. It deliberately excludes the raw `ply` counter because the current Crownline rules do not use absolute ply count to determine legal moves, scoring, cooldown behavior, line retirement, quota handling, or terminal status.

Consequently, positions reached at different historical move numbers serialize identically when every future-relevant rule fact is the same.

A future replay or audit envelope may carry move number, move history, timestamps, or provenance around a CLSN position. Those are intentionally separate from position identity.

Likewise, CLSN1 does not encode the surrounding two-game **set**: participant-to-color mapping, completed Game 1 score, carry score, and set index belong to a future set-state envelope. This separation keeps a Game 1 or Game 2 position independently reusable in an AI test suite.

## Canonicalization and parsing

The implementation is in `crownline_state_notation.py`:

```python
from crownline_state_notation import (
    canonicalize_clsn,
    parse_clsn,
    serialize_clsn,
)

text = serialize_clsn(game)
restored = parse_clsn(text)
assert serialize_clsn(restored) == text
```

The parser may accept fields, board tokens, or cooldown entries in a different order, but `serialize_clsn()` always emits the single canonical representation.

Invalid states are rejected rather than silently normalized when they violate notation-level invariants such as duplicate piece identities, an unplayable square for the selected geometry, an invalid Crownline, or an impossible cooldown value.

## Fingerprints

Opaque hashes are derived **from the notation**, not treated as the primary state representation:

```python
from crownline_state_notation import clsn_fingerprint

fingerprint = clsn_fingerprint(game)
```

Conceptually:

```text
Crownline position
        ↓
canonical CLSN1
        ↓
SHA-256 fingerprint
```

This gives exact-state comparison a readable and reversible source of truth.

## Benchmarking consequence

The next benchmark-fixture revision should store canonical Game 1 and Game 2 CLSN positions directly. Opening-generation traces can remain useful provenance, but the benchmark input should be the frozen position itself, not the procedure that happened to generate it.

That allows future suites to include reproducible categories such as early development, capture pressure, promotion races, Sovereign-choice positions, Crownline construction/denial, cooldown management, quota pressure, late-game positions, and known repetition-prone states.

`CLSN1` therefore becomes the state boundary beneath the future Crownline position suite.
