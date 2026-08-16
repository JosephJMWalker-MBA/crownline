import * as THREE from 'three';
import { EffectComposer } from 'https://cdn.jsdelivr.net/npm/three@0.185.1/examples/jsm/postprocessing/EffectComposer.js';
import { RenderPass } from 'https://cdn.jsdelivr.net/npm/three@0.185.1/examples/jsm/postprocessing/RenderPass.js';
import { SSAOPass } from 'https://cdn.jsdelivr.net/npm/three@0.185.1/examples/jsm/postprocessing/SSAOPass.js';
import { UnrealBloomPass } from 'https://cdn.jsdelivr.net/npm/three@0.185.1/examples/jsm/postprocessing/UnrealBloomPass.js';
import { SMAAPass } from 'https://cdn.jsdelivr.net/npm/three@0.185.1/examples/jsm/postprocessing/SMAAPass.js';
import { OutputPass } from 'https://cdn.jsdelivr.net/npm/three@0.185.1/examples/jsm/postprocessing/OutputPass.js';
import { RoomEnvironment } from 'https://cdn.jsdelivr.net/npm/three@0.185.1/examples/jsm/environments/RoomEnvironment.js';

// Graphics Sprint 1 deliberately lives beside the authoritative game renderer.
// It enhances WebGLRenderer at the presentation boundary without touching rules,
// state, move generation, or the browser controller's interaction model.

const GRAPHICS_STATE = Symbol.for('crownline.graphics.state');
const proto = THREE.WebGLRenderer.prototype;
const nativeRender = proto.render;
const nativeSetSize = proto.setSize;
const nativeSetPixelRatio = proto.setPixelRatio;

const constrainedDevice = Boolean(
  (navigator.deviceMemory && navigator.deviceMemory <= 4) ||
  (navigator.hardwareConcurrency && navigator.hardwareConcurrency <= 4)
);
const prefersReducedMotion = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false;
const quality = constrainedDevice ? 'standard' : 'premium';
const maxPixelRatio = constrainedDevice ? 1.5 : 2;

function capPixelRatio(value) {
  return Math.max(1, Math.min(Number(value) || 1, maxPixelRatio));
}

proto.setPixelRatio = function crownlineSetPixelRatio(value) {
  return nativeSetPixelRatio.call(this, capPixelRatio(value));
};

function tuneShadows(scene) {
  scene.traverse((object) => {
    if (!object.isDirectionalLight || !object.castShadow) return;
    object.shadow.bias = -0.00035;
    object.shadow.normalBias = 0.022;
    object.shadow.camera.near = 1;
    object.shadow.camera.far = 28;
    object.shadow.mapSize.set(constrainedDevice ? 1024 : 2048, constrainedDevice ? 1024 : 2048);
    object.shadow.camera.updateProjectionMatrix?.();
  });
}

function tunePbrMaterials(scene) {
  scene.traverse((object) => {
    if (!object.material) return;
    const materials = Array.isArray(object.material) ? object.material : [object.material];
    for (const material of materials) {
      if (!material?.isMeshStandardMaterial) continue;
      material.envMapIntensity = object.isMesh && object.geometry?.type === 'PlaneGeometry' ? 0.32 : 0.68;
      material.needsUpdate = true;
    }
  });
}

function setupEnvironment(renderer, scene, state) {
  const environment = new RoomEnvironment();
  const pmrem = new THREE.PMREMGenerator(renderer);
  pmrem.compileCubemapShader?.();
  const target = pmrem.fromScene(environment, 0.045);
  scene.environment = target.texture;
  if ('environmentIntensity' in scene) scene.environmentIntensity = 0.58;
  environment.dispose();
  pmrem.dispose();
  state.environmentTarget = target;
  tunePbrMaterials(scene);
}

function setupComposer(renderer, scene, camera, state) {
  const size = renderer.getSize(new THREE.Vector2());
  const width = Math.max(1, size.x);
  const height = Math.max(1, size.y);

  const composer = new EffectComposer(renderer);
  composer.setPixelRatio?.(renderer.getPixelRatio());
  composer.setSize(width, height);

  const renderPass = new RenderPass(scene, camera);
  composer.addPass(renderPass);

  const ssaoPass = new SSAOPass(scene, camera, width, height);
  ssaoPass.kernelRadius = 7;
  ssaoPass.minDistance = 0.0025;
  ssaoPass.maxDistance = 0.075;
  ssaoPass.enabled = !constrainedDevice;
  composer.addPass(ssaoPass);

  // Bloom is intentionally thresholded so ordinary board lighting does not glow.
  // It should primarily catch Kings, Crownline events, and other emissive accents.
  const bloomPass = new UnrealBloomPass(
    new THREE.Vector2(width, height),
    constrainedDevice ? 0.12 : 0.22,
    0.30,
    1.02
  );
  bloomPass.enabled = !prefersReducedMotion || !constrainedDevice;
  composer.addPass(bloomPass);

  // EffectComposer renders to an offscreen target, so restore clean edge quality
  // before the final output transform rather than relying only on canvas MSAA.
  const smaaPass = new SMAAPass();
  composer.addPass(smaaPass);

  // OutputPass owns tone mapping + sRGB conversion at the end of the chain.
  const outputPass = new OutputPass();
  composer.addPass(outputPass);

  state.composer = composer;
  state.ssaoPass = ssaoPass;
  state.bloomPass = bloomPass;
  state.smaaPass = smaaPass;
  state.lastWidth = width;
  state.lastHeight = height;
}

function setupGraphics(renderer, scene, camera) {
  const state = {
    bypass: true,
    inComposer: false,
    failed: false,
    composer: null,
    environmentTarget: null,
    lastWidth: 0,
    lastHeight: 0,
  };
  renderer[GRAPHICS_STATE] = state;

  try {
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.toneMapping = THREE.AgXToneMapping;
    renderer.toneMappingExposure = 1.08;
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;

    tuneShadows(scene);
    setupEnvironment(renderer, scene, state);
    setupComposer(renderer, scene, camera, state);

    state.bypass = false;
    renderer.compileAsync?.(scene, camera).catch(() => {});

    window.CrownlineGraphics = {
      quality,
      ambientOcclusion: state.ssaoPass.enabled,
      bloom: state.bloomPass.enabled,
      environmentLighting: true,
      toneMapping: 'AgX',
    };
    window.dispatchEvent(new CustomEvent('crownline-graphics-ready', {
      detail: { ...window.CrownlineGraphics },
    }));
    return state;
  } catch (error) {
    state.failed = true;
    state.bypass = false;
    console.warn('Crownline graphics enhancement unavailable; using base renderer.', error);
    return state;
  }
}

proto.setSize = function crownlineSetSize(width, height, updateStyle = true) {
  const state = this[GRAPHICS_STATE];
  if (
    state?.composer &&
    state.lastWidth === width &&
    state.lastHeight === height
  ) {
    return this;
  }

  const result = nativeSetSize.call(this, width, height, updateStyle);
  if (state?.composer) {
    state.lastWidth = width;
    state.lastHeight = height;
    state.composer.setSize(width, height);
  }
  return result;
};

proto.render = function crownlineRender(scene, camera) {
  let state = this[GRAPHICS_STATE];
  if (state?.bypass || state?.inComposer || state?.failed) {
    return nativeRender.call(this, scene, camera);
  }

  if (!state) state = setupGraphics(this, scene, camera);
  if (state.failed || !state.composer) return nativeRender.call(this, scene, camera);

  try {
    state.inComposer = true;
    state.composer.render();
  } catch (error) {
    state.failed = true;
    console.warn('Crownline post-processing failed; reverting to base renderer.', error);
    return nativeRender.call(this, scene, camera);
  } finally {
    state.inComposer = false;
  }
};

window.addEventListener('beforeunload', () => {
  // Renderer-owned state is intentionally disposed only on page teardown. The
  // board itself is recreated frequently during play and should retain IBL.
  const canvas = document.querySelector('#board');
  if (!canvas) return;
  // No global renderer handle is exposed by main.js, so GPU resources are also
  // reclaimed naturally with the WebGL context when this document unloads.
});
