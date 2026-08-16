# Crownline Graphics Upgrade

**Status:** Graphics Sprint 2 — Premium Tabletop implemented. Gameplay rules are unaffected.

Crownline's visual direction is **premium tabletop object**: tactile, legible, restrained, and materially rich. Graphics work must never make piece identity, legal moves, Crown nodes, cooldown state, or Crownline geometry harder to read.

## Architecture boundary

Graphics remain non-authoritative.

```text
Python rules/state
      ↓
serialized game state
      ↓
existing browser controller
      ↓
Three.js board renderer
      ↓
graphics enhancement / post-processing
      ↓
screen
```

No graphics code decides legal moves, scoring, Crownline eligibility, cooldowns, line retirement, set state, or AI behavior.

`main.js` continues to create the playable scene from authoritative state. `web/graphics.js` enhances the resulting Three.js objects at the presentation boundary. Because `main.js` rebuilds dynamic tiles and pieces after state changes, the graphics layer tracks and upgrades newly created meshes without maintaining a second game state.

---

## Sprint 1 — rendering foundation

### Renderer and output

- sRGB output color space;
- AgX tone mapping with restrained exposure;
- device-aware pixel-ratio cap;
- tuned directional-light shadow bias and normal bias;
- base renderer remains the fallback if the enhancement pipeline fails.

### Image-based lighting

A Three.js `RoomEnvironment` is converted through `PMREMGenerator` and assigned to the scene environment. PBR materials therefore receive image-based reflections and diffuse illumination without requiring an external HDR asset or introducing a new asset-license dependency.

### Post-processing chain

```text
RenderPass
  → SSAOPass
  → UnrealBloomPass
  → SMAAPass
  → OutputPass
```

- **SSAO** is subtle and disabled automatically on constrained devices.
- **Bloom** uses a high threshold and low strength so ordinary board lighting stays clean.
- **SMAA** restores clean edge treatment after offscreen post-processing.
- **OutputPass** performs final tone mapping and color-space conversion.

Human review after Sprint 1 was important: the presentation remained attractive and stable, but the visual difference was not immediately obvious. That result was treated as evidence to improve object construction rather than simply increasing bloom/AO intensity.

---

## Sprint 2 — Premium Tabletop

The second sprint deliberately changes the physical language of the scene while preserving every gameplay interaction.

### Board construction

- the monolithic board base is upgraded to a rounded, lacquered dark-walnut-style body;
- four raised frame rails create a clearly constructed perimeter rather than a simple box slab;
- a restrained brass inner trim line gives the playing surface a premium inlaid edge;
- the inner deck remains darker and less reflective than the frame so the board surface stays visually quiet.

### Crown-square inlays

Crown nodes now receive a materially distinct treatment rather than only a color change:

- rounded geometry;
- blue-gray enamel / lacquer response;
- stronger clearcoat than ordinary squares;
- a thin metallic border inlay;
- existing printed Crown value and algebraic notation remain untouched and authoritative to the existing UI renderer.

The inlay must read as part of the physical board before any glow effect is active.

### Piece silhouette

Ordinary pieces are upgraded from straight cylinders to a lathed checker / casino-chip profile with:

- rounded shoulders;
- a wider tactile rim;
- two subtle edge grooves;
- differentiated ivory and charcoal material response;
- restrained clearcoat so pieces feel manufactured rather than plastic-shiny.

The printed piece identity remains the primary information layer and is not replaced by the graphics module.

### King silhouette

A King must be recognizable without depending on emissive glow.

The procedural King treatment therefore adds:

- a taller lathed base profile;
- metallic coronet band;
- six physical crown points around the perimeter;
- retained gold halo / accent behavior for state feedback;
- richer metal response under the Sprint 1 environment lighting.

The crown points stay around the outer rim so the numbered top face remains readable.

### Dynamic-scene behavior

`main.js` recreates dynamic pieces and tiles after authoritative moves. Sprint 2 therefore uses `WeakSet` tracking inside `graphics.js` to enhance only newly created meshes before a rendered frame. This keeps the graphics layer idempotent and avoids duplicating decorations on every animation frame.

---

## Performance posture

The graphics layer distinguishes `premium` and `standard` device profiles using conservative browser hardware signals.

On constrained devices:

- pixel ratio caps lower;
- shadow-map resolution lowers;
- SSAO is disabled;
- bloom strength is reduced.

Procedural geometry is intentionally modest in scale: Crownline has a small number of pieces and a fixed 8×8 board, so rounded boxes and lathed pieces remain bounded rather than scaling with a large world.

The game remains authoritative and playable even if the post-processing layer cannot initialize.

---

## Visual acceptance criteria

A graphics improvement stays only if all of these remain true:

1. White and Black pieces are immediately distinguishable.
2. Printed piece identities remain easy to read.
3. A King is recognizable by silhouette before noticing its glow.
4. Crown squares look physically different from ordinary squares.
5. Green legal moves and amber capture moves remain unambiguous.
6. Crownline hover previews remain spatially obvious.
7. Cooldown superscripts remain legible.
8. Bloom does not wash out white pieces or Crown-square numbers.
9. Ambient occlusion does not turn Black pieces into featureless silhouettes.
10. The game remains smooth during board rotation and move animation.
11. The new frame does not visually compete with the Crown Grid.
12. Reloading the page should produce an immediately perceptible visual change from the pre-Sprint-2 board.

---

## Next graphics stages

### Sprint 2B — review and retune

Human play decides whether the new physical language is correct before adding assets.

Watch for:

- whether the walnut/brass frame feels premium rather than ornamental;
- whether Crown-square inlays remain readable in both Game 1 and Game 2;
- whether Black-piece grooves retain enough contrast;
- whether King crown points are obvious but do not obscure piece numbers;
- whether new geometry remains smooth during captures and promotion;
- whether frame/inlay reflections are excessive under rotation.

Prefer material/silhouette correction over adding stronger effects.

### Sprint 3 — authored hero assets

Only after the procedural visual language is approved:

- model the board body in Blender;
- model a purpose-built Crownline piece silhouette;
- model the final King treatment;
- export through glTF 2.0;
- load with Three.js `GLTFLoader`;
- preserve current procedural geometry as a fallback and development asset set.

The procedural pass is therefore also an art-direction prototype for the authored models.

### Sprint 4 — optional polish

Evaluate rather than assume:

- selected-object outlines;
- higher-end ambient occlusion;
- alternate environments;
- graphics quality control exposed in the UI;
- subtle authored surface normal/roughness textures;
- authored capture-bank props;
- restrained sound/visual synchronization for Crownline and Royal events.

Do not add particle clutter or cinematic effects merely because the renderer can support them.
