import * as THREE from 'three';

// Final visibility pass for the state-aware King glow. Premium Tabletop owns
// the semantic state and event logic; this module makes sure the aura remains
// visibly readable at real board scale without turning the King into neon.

const priorGroupAdd = THREE.Group.prototype.add;
const trackedKingGroups = new Set();
const rulesMode = document.querySelector('#rules-mode');
const prefersReducedMotion = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false;

function registerKingGroup(group) {
  const glow = group?.userData?.kingGlow;
  if (!glow?.aura?.material) return;

  trackedKingGroups.add(group);

  // The original aura sat almost exactly on the board surface, which made it
  // disappear into depth testing at normal camera angles. Raise it enough to
  // clear the tiles while keeping it visibly beneath the physical checker.
  glow.aura.position.y = -0.108;
  glow.aura.renderOrder = 0;
  glow.aura.material.depthWrite = false;
  glow.aura.material.depthTest = true;
  glow.aura.material.transparent = true;
  glow.aura.material.blending = THREE.AdditiveBlending;
  glow.aura.material.color?.setHex?.(0xffe1a6);
  glow.aura.material.needsUpdate = true;
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
    if (!glow?.aura?.material) continue;

    const cooling = cooldownMode && Number(glow.cooldown || 0) > 0;
    const ready = cooldownMode && !cooling;
    const pulse = prefersReducedMotion
      ? 0.5
      : 0.5 + 0.5 * Math.sin(time * 0.00175 + Number(glow.pulseOffset || 0));

    // These are minimum readable values. Premium Tabletop can still exceed
    // them for hover, selection, promotion, readiness and Crownline events.
    const targetOpacity = cooldownMode
      ? (ready ? 0.155 + pulse * 0.030 : 0.072)
      : 0.108;
    const targetScale = cooldownMode
      ? (ready ? 1.075 + pulse * 0.035 : 1.015)
      : 1.045;
    const targetRim = cooldownMode
      ? (ready ? 0.185 + pulse * 0.040 : 0.078)
      : 0.105;
    const targetBody = cooldownMode
      ? (ready ? 0.068 + pulse * 0.014 : 0.034)
      : 0.048;

    glow.aura.material.opacity = Math.min(
      0.34,
      Math.max(targetOpacity, Number(glow.aura.material.opacity || 0))
    );
    glow.aura.scale.setScalar(Math.max(targetScale, Number(glow.aura.scale.x || 1)));

    for (const trim of glow.trims || []) {
      if (trim?.material?.emissiveIntensity !== undefined) {
        trim.material.emissiveIntensity = Math.max(
          targetRim,
          Number(trim.material.emissiveIntensity || 0)
        );
      }
    }

    if (glow.body?.material?.emissiveIntensity !== undefined) {
      glow.body.material.emissiveIntensity = Math.max(
        targetBody,
        Number(glow.body.material.emissiveIntensity || 0)
      );
    }
  }

  requestAnimationFrame(animateKingGlowVisibility);
}

requestAnimationFrame(animateKingGlowVisibility);

window.CrownlineKingGlowVisibility = {
  active: true,
  version: 1,
  intent: 'readable-state-aware-king-glow',
};
