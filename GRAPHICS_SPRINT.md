# Crownline Graphics Upgrade

**Status:** Graphics Sprint 1A/1B implemented. Gameplay rules are unaffected.

Crownline's visual direction is **premium tabletop object**: tactile, legible, restrained, and materially rich. Graphics work must never make piece identity, legal moves, Crown nodes, cooldown state, or Crownline geometry harder to read.

## Implemented foundation

`web/graphics.js` adds a presentation-only enhancement layer before the existing Three.js board renderer.

### Renderer and output

- sRGB output color space;
- AgX tone mapping with deliberately restrained exposure;
- device-aware pixel-ratio cap;
- tuned directional-light shadow bias and normal bias;
- existing renderer remains the fallback if the enhancement pipeline fails.

### Image-based lighting

A Three.js `RoomEnvironment` is converted through `PMREMGenerator` and assigned to the scene environment. Existing PBR materials therefore receive image-based reflections and diffuse illumination without requiring an external HDR asset or introducing a new asset-license dependency.

### Post-processing chain

The current pass order is:

```text
RenderPass
  → SSAOPass
  → UnrealBloomPass
  → SMAAPass
  → OutputPass
```

- **SSAO** is subtle and disabled automatically on constrained devices.
- **Bloom** uses a high threshold and low strength so normal board lighting should remain clean; emissive King/Crownline accents receive most of the effect.
- **SMAA** restores clean edge treatment after rendering through offscreen post-processing targets.
- **OutputPass** performs the final tone mapping and color-space conversion.

### Performance posture

The graphics layer distinguishes `premium` and `standard` device profiles using conservative browser hardware signals.

On constrained devices:

- pixel ratio caps lower;
- shadow-map resolution lowers;
- SSAO is disabled;
- bloom strength is reduced.

The game remains authoritative and playable even if the graphics layer cannot initialize.

## Visual acceptance criteria

A graphics improvement stays only if all of these remain true:

1. White and Black pieces are immediately distinguishable.
2. Printed piece identities remain easy to read.
3. Kings are visually special without becoming noisy.
4. Crown squares remain distinct from ordinary board squares.
5. Green legal moves and amber capture moves remain unambiguous.
6. Crownline hover previews remain spatially obvious.
7. Cooldown superscripts remain legible.
8. Bloom does not wash out white pieces or Crown-square numbers.
9. Ambient occlusion does not turn Black pieces into featureless silhouettes.
10. The game remains smooth during board rotation and move animation.

## Next graphics stages

### Sprint 1C — material refinement

Keep the current geometry, but improve material separation:

- board surround: lacquered dark wood / composite feel;
- inset: lower-reflectivity contrasting material;
- playable squares: differentiated matte surfaces;
- Crown nodes: subtle premium inlay treatment;
- ordinary pieces: ceramic/resin feel;
- King metal: `MeshPhysicalMaterial` with restrained clearcoat/metal response.

The goal is not photorealism for its own sake. The goal is that different materials react differently enough to feel physically intentional.

### Sprint 1D — lighting and interaction polish

- retune key/rim balance after material pass;
- make selected-piece treatment feel integrated with the physical board;
- retune Crownline score glow under bloom;
- tune Royal Crownline as the strongest visual event in the game;
- consider a very subtle camera/light response during promotion and set transitions.

### Sprint 2 — authored hero assets

Only after the rendering/material foundation is stable:

- model board body in Blender;
- model a purpose-built Crownline piece silhouette;
- model a distinctive King treatment;
- export through glTF 2.0;
- load with Three.js `GLTFLoader`;
- preserve current procedural geometry as a fallback and development asset set.

### Sprint 3 — optional polish

Evaluate rather than assume:

- selected-object outlines;
- higher-end ambient occlusion;
- alternate environments;
- graphics quality control exposed in the UI;
- subtle surface normal/roughness textures;
- authored capture-bank props.

Do not add particle clutter or cinematic effects merely because the renderer can support them.

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
