import * as THREE from 'three';

// Premium Tabletop owns King state semantics. This module guarantees that the
// semantic glow is actually legible at normal board scale. The first pass put
// most of its energy beneath the physical checker, so the visible remainder was
// effectively imperceptible. This pass adds a soft donut-shaped contact halo
// whose brightest band lives just outside the piece silhouette.

const priorGroupAdd = THREE.Group.prototype.add;
const trackedKingGroups = new Set();
const rulesMode = document.querySelector('#rules-mode');
const prefersReducedMotion = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false;

function createContactHalo() {
  const material = new THREE.ShaderMaterial({
    transparent: true,
    depthWrite: false,
    depthTest: true,
    blending: THREE.AdditiveBlending,
    side: THREE.DoubleSide,
    uniforms: {
      uColor: { value: new THREE.Color(0xffd58a) },
      uOpacity: { value: 0.18 },
    },
    vertexShader: `
      varying vec2 vUv;
      void main() {
        vUv = uv;
        gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
      }
    `,
    fragmentShader: `
      uniform vec3 uColor;
      uniform float uOpacity;
      varying vec2 vUv;

      void main() {
        vec2 p = vUv - 0.5;
        float radius = length(p) * 2.0;

        // Transparent beneath the checker; strongest just beyond its edge;
        // feather gradually into the square rather than drawing a hard ring.
        float inner = smoothstep(0.52, 0.63, radius);
        float outer = 1.0 - smoothstep(0.76, 1.00, radius);
        float halo = inner * outer;
        halo *= 0.70 + 0.30 * (1.0 - smoothstep(0.63, 0.88, radius));

        if (halo <= 0.002) discard;
        gl_FragColor = vec4(uColor, halo * uOpacity);
      }
    `,
  });
  material.toneMapped = false;

  const halo = new THREE.Mesh(new THREE.PlaneGeometry(1.58, 1.58), material);
  halo.rotation.x = -Math.PI / 2;
  // King groups sit at y=.235. This places the halo at world y≈.087: above
  // even raised Crown tiles, while still visually contacting the board.
  halo.position.y = -0.148;
  halo.renderOrder = 1;
  halo.userData.premiumManaged = true;
  halo.userData.kingContactHalo = true;
  return halo;
}

function registerKingGroup(group) {
  const glow = group?.userData?.kingGlow;
  if (!glow?.aura?.material) return;

  trackedKingGroups.add(group);

  // Keep the original broad aura as the soft secondary layer, but position it
  // at the board contact plane instead of high beneath the checker body.
  glow.aura.position.y = -0.151;
  glow.aura.renderOrder = 0;
  glow.aura.material.depthWrite = false;
  glow.aura.material.depthTest = true;
  glow.aura.material.transparent = true;
  glow.aura.material.blending = THREE.AdditiveBlending;
  glow.aura.material.color?.setHex?.(0xffdf9d);
  glow.aura.material.needsUpdate = true;

  if (!glow.contactHalo) {
    glow.contactHalo = createContactHalo();
    // Call the previous Group.add directly so this registration step cannot
    // recurse back through itself.
    priorGroupAdd.call(group, glow.contactHalo);
  }
}

THREE.Group.prototype.add = function crownlineKingGlowVisibilityAdd(...objects) {
  const result = priorGroupAdd.apply(this, objects);
  registerKingGroup(this);
  return result;
};

function cleanup() {
  for (const group of trackedKingGroups) {
    if (!group?.parent) trackedKingGroups.delete(group);
  }
}

function animateKingGlowVisibility(time = 0) {
  cleanup();

  const mode = rulesMode?.value;
  const cooldownMode = mode === 'candidate' || mode === 'crowned';

  for (const group of trackedKingGroups) {
    const glow = group?.userData?.kingGlow;
    if (!glow?.aura?.material || !glow.contactHalo?.material?.uniforms) continue;

    const cooling = cooldownMode && Number(glow.cooldown || 0) > 0;
    const ready = cooldownMode && !cooling;
    const pulse = prefersReducedMotion
      ? 0.5
      : 0.5 + 0.5 * Math.sin(time * 0.00165 + Number(glow.pulseOffset || 0));

    // The contact halo is intentionally unmistakable but restrained. Cooling
    // Kings remain present; ready Kings quietly breathe. Official v1.0 Kings
    // still get a stable aura because kingship itself should remain readable.
    let contactOpacity = cooldownMode
      ? (ready ? 0.255 + pulse * 0.055 : 0.115)
      : 0.185;
    let contactScale = cooldownMode
      ? (ready ? 1.015 + pulse * 0.025 : 0.985)
      : 1.000;
    let auraOpacity = cooldownMode
      ? (ready ? 0.185 + pulse * 0.030 : 0.085)
      : 0.130;
    let rimIntensity = cooldownMode
      ? (ready ? 0.245 + pulse * 0.050 : 0.105)
      : 0.155;
    let bodyIntensity = cooldownMode
      ? (ready ? 0.082 + pulse * 0.018 : 0.040)
      : 0.058;

    // Premium Tabletop marks hover/selection on the same King group. Mirror
    // those conditions here so the visible floor responds, rather than being
    // overwritten by the semantic animation loop on the next frame.
    const square = group.userData?.premiumKingSquare;
    const hovered = Boolean(square && window.CrownlinePremiumTabletop?.hoveredKingSquare === square);
    const selected = Boolean(square && window.CrownlinePremiumTabletop?.selectedKingSquare === square);
    if (hovered) {
      contactOpacity += 0.055;
      contactScale += 0.018;
      auraOpacity += 0.030;
      rimIntensity += 0.060;
    }
    if (selected) {
      contactOpacity += 0.085;
      contactScale += 0.026;
      auraOpacity += 0.050;
      rimIntensity += 0.095;
      bodyIntensity += 0.020;
    }

    // Premium Tabletop already owns event timing. Reuse it here so promotion,
    // readiness, Crownline, and Royal moments also brighten the visible halo.
    if (time < Number(glow.eventUntil || 0)) {
      const duration = Math.max(1, Number(glow.eventUntil || 0) - Number(glow.eventStart || 0));
      const phase = THREE.MathUtils.clamp((time - Number(glow.eventStart || 0)) / duration, 0, 1);
      const flare = Math.sin(Math.PI * phase) * Number(glow.eventStrength || 0);
      contactOpacity += flare * 0.20;
      contactScale += flare * 0.055;
      auraOpacity += flare * 0.10;
      rimIntensity += flare * 0.22;
      bodyIntensity += flare * 0.045;
    }

    glow.contactHalo.material.uniforms.uOpacity.value = Math.min(0.52, contactOpacity);
    glow.contactHalo.scale.setScalar(contactScale);

    // The broad aura remains softer than the contact halo; it gives the ring a
    // falloff instead of allowing it to read as a selection indicator.
    glow.aura.material.opacity = Math.min(
      0.34,
      Math.max(auraOpacity, Number(glow.aura.material.opacity || 0))
    );
    glow.aura.scale.setScalar(Math.max(1.02, Number(glow.aura.scale.x || 1)));

    for (const trim of glow.trims || []) {
      if (trim?.material?.emissiveIntensity !== undefined) {
        trim.material.emissiveIntensity = Math.max(
          rimIntensity,
          Number(trim.material.emissiveIntensity || 0)
        );
      }
    }

    if (glow.body?.material?.emissiveIntensity !== undefined) {
      glow.body.material.emissiveIntensity = Math.max(
        bodyIntensity,
        Number(glow.body.material.emissiveIntensity || 0)
      );
    }
  }

  requestAnimationFrame(animateKingGlowVisibility);
}

requestAnimationFrame(animateKingGlowVisibility);

window.CrownlineKingGlowVisibility = {
  active: true,
  version: 2,
  intent: 'visible-soft-contact-halo-plus-state-aware-glow',
};
