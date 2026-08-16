import * as THREE from 'three';
import { EffectComposer } from 'https://cdn.jsdelivr.net/npm/three@0.185.1/examples/jsm/postprocessing/EffectComposer.js';
import { RenderPass } from 'https://cdn.jsdelivr.net/npm/three@0.185.1/examples/jsm/postprocessing/RenderPass.js';
import { SSAOPass } from 'https://cdn.jsdelivr.net/npm/three@0.185.1/examples/jsm/postprocessing/SSAOPass.js';
import { UnrealBloomPass } from 'https://cdn.jsdelivr.net/npm/three@0.185.1/examples/jsm/postprocessing/UnrealBloomPass.js';
import { SMAAPass } from 'https://cdn.jsdelivr.net/npm/three@0.185.1/examples/jsm/postprocessing/SMAAPass.js';
import { OutputPass } from 'https://cdn.jsdelivr.net/npm/three@0.185.1/examples/jsm/postprocessing/OutputPass.js';
import { RoomEnvironment } from 'https://cdn.jsdelivr.net/npm/three@0.185.1/examples/jsm/environments/RoomEnvironment.js';
import { RoundedBoxGeometry } from 'https://cdn.jsdelivr.net/npm/three@0.185.1/examples/jsm/geometries/RoundedBoxGeometry.js';

// Crownline graphics remain strictly presentation-side. The authoritative Python
// engine and the browser controller continue to own all game state and rules.

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

function physicalMaterial(options) {
  return new THREE.MeshPhysicalMaterial({
    clearcoat: 0,
    clearcoatRoughness: 0.3,
    envMapIntensity: 0.72,
    ...options,
  });
}

function disposeMaterial(material) {
  if (!material) return;
  if (Array.isArray(material)) material.forEach((entry) => entry?.dispose?.());
  else material.dispose?.();
}

function replaceGeometry(mesh, geometry) {
  mesh.geometry?.dispose?.();
  mesh.geometry = geometry;
}

function replaceMaterial(mesh, material) {
  disposeMaterial(mesh.material);
  mesh.material = material;
}

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
      if (material.envMapIntensity === undefined) material.envMapIntensity = 0.68;
      material.needsUpdate = true;
    }
  });
}

function roundedFrameRail(width, depth, material) {
  const rail = new THREE.Mesh(
    new RoundedBoxGeometry(width, 0.19, depth, 4, 0.055),
    material.clone()
  );
  rail.castShadow = true;
  rail.receiveShadow = true;
  return rail;
}

function addPremiumFrame(boardBase, state) {
  const boardGroup = boardBase.parent;
  if (!boardGroup || boardGroup.userData.premiumTabletopFrame) return;
  boardGroup.userData.premiumTabletopFrame = true;

  replaceGeometry(boardBase, new RoundedBoxGeometry(8.82, 0.42, 8.82, 5, 0.12));
  replaceMaterial(boardBase, physicalMaterial({
    color: 0x241a13,
    roughness: 0.34,
    metalness: 0.04,
    clearcoat: 0.42,
    clearcoatRoughness: 0.24,
    envMapIntensity: 0.78,
  }));
  boardBase.position.y = -0.29;

  const walnut = physicalMaterial({
    color: 0x302118,
    roughness: 0.30,
    metalness: 0.03,
    clearcoat: 0.55,
    clearcoatRoughness: 0.22,
    envMapIntensity: 0.82,
  });

  const north = roundedFrameRail(8.46, 0.30, walnut);
  north.position.set(0, -0.015, -4.13);
  const south = north.clone();
  south.material = walnut.clone();
  south.position.z = 4.13;
  const west = roundedFrameRail(0.30, 8.46, walnut);
  west.position.set(-4.13, -0.015, 0);
  const east = west.clone();
  east.material = walnut.clone();
  east.position.x = 4.13;

  const brass = physicalMaterial({
    color: 0xb58b45,
    roughness: 0.24,
    metalness: 0.82,
    clearcoat: 0.18,
    envMapIntensity: 0.95,
  });
  const trimPieces = [
    [new THREE.BoxGeometry(8.03, 0.028, 0.034), 0, 0.075, -4.00],
    [new THREE.BoxGeometry(8.03, 0.028, 0.034), 0, 0.075, 4.00],
    [new THREE.BoxGeometry(0.034, 0.028, 8.03), -4.00, 0.075, 0],
    [new THREE.BoxGeometry(0.034, 0.028, 8.03), 4.00, 0.075, 0],
  ].map(([geometry, x, y, z]) => {
    const mesh = new THREE.Mesh(geometry, brass.clone());
    mesh.position.set(x, y, z);
    mesh.castShadow = true;
    return mesh;
  });

  boardGroup.add(north, south, west, east, ...trimPieces);
  walnut.dispose();
  brass.dispose();
  state.frameObjects.push(north, south, west, east, ...trimPieces);
}

function addCrownInlay(tile, state) {
  if (tile.userData.premiumCrownInlay) return;
  tile.userData.premiumCrownInlay = true;

  const outer = new THREE.Shape();
  outer.moveTo(-0.445, -0.445);
  outer.lineTo(0.445, -0.445);
  outer.lineTo(0.445, 0.445);
  outer.lineTo(-0.445, 0.445);
  outer.closePath();

  const inner = new THREE.Path();
  inner.moveTo(-0.385, -0.385);
  inner.lineTo(-0.385, 0.385);
  inner.lineTo(0.385, 0.385);
  inner.lineTo(0.385, -0.385);
  inner.closePath();
  outer.holes.push(inner);

  const border = new THREE.Mesh(
    new THREE.ShapeGeometry(outer),
    physicalMaterial({
      color: 0xb58b45,
      roughness: 0.25,
      metalness: 0.78,
      clearcoat: 0.20,
      envMapIntensity: 0.98,
      side: THREE.DoubleSide,
    })
  );
  border.rotation.x = -Math.PI / 2;
  border.position.y = 0.086;
  border.receiveShadow = true;
  tile.add(border);
  state.decorativeObjects.add(border);
}

function enhanceTile(tile, state) {
  if (state.processedMeshes.has(tile)) return;
  const params = tile.geometry?.parameters;
  if (!params || tile.userData?.kind !== 'square') return;

  const height = Number(params.height || 0.10);
  const crown = height > 0.12;
  replaceGeometry(tile, new RoundedBoxGeometry(0.965, crown ? 0.145 : 0.10, 0.965, 3, crown ? 0.055 : 0.035));

  if (crown) {
    replaceMaterial(tile, physicalMaterial({
      color: 0x516b82,
      emissive: tile.userData.playable ? 0x101a27 : 0x000000,
      emissiveIntensity: tile.userData.playable ? 0.28 : 0,
      roughness: 0.23,
      metalness: 0.12,
      clearcoat: 0.76,
      clearcoatRoughness: 0.18,
      envMapIntensity: 0.92,
      opacity: tile.userData.playable ? 1 : 0.52,
      transparent: !tile.userData.playable,
    }));
    addCrownInlay(tile, state);
  } else {
    const sourceColor = tile.material?.color?.getHex?.() ?? 0x252c37;
    const dark = sourceColor < 0x808080;
    replaceMaterial(tile, physicalMaterial({
      color: dark ? 0x252c35 : 0xcfc7b8,
      roughness: dark ? 0.50 : 0.58,
      metalness: 0.025,
      clearcoat: dark ? 0.12 : 0.08,
      clearcoatRoughness: 0.50,
      envMapIntensity: dark ? 0.48 : 0.42,
      opacity: tile.userData.playable ? 1 : 0.39,
      transparent: !tile.userData.playable,
    }));
  }

  state.processedMeshes.add(tile);
}

function checkerProfile(king) {
  if (king) {
    return [
      [0.00, -0.15], [0.31, -0.15], [0.38, -0.13], [0.42, -0.08],
      [0.43, -0.02], [0.41, 0.05], [0.37, 0.09], [0.39, 0.13],
      [0.36, 0.17], [0.30, 0.19], [0.00, 0.19],
    ];
  }
  return [
    [0.00, -0.115], [0.31, -0.115], [0.38, -0.095], [0.415, -0.055],
    [0.425, 0.00], [0.405, 0.055], [0.37, 0.085], [0.31, 0.115],
    [0.00, 0.115],
  ];
}

function addPieceGrooves(body, owner, state) {
  if (body.userData.premiumGrooves) return;
  body.userData.premiumGrooves = true;
  const accent = owner === 'W' ? 0xcfc4af : 0x323b48;
  for (const y of [-0.055, 0.055]) {
    const groove = new THREE.Mesh(
      new THREE.TorusGeometry(0.385, 0.012, 8, 48),
      physicalMaterial({
        color: accent,
        roughness: 0.24,
        metalness: owner === 'W' ? 0.08 : 0.28,
        clearcoat: 0.35,
        envMapIntensity: 0.72,
      })
    );
    groove.rotation.x = Math.PI / 2;
    groove.position.y = y;
    body.add(groove);
    state.decorativeObjects.add(groove);
  }
}

function enhanceKingGroup(group, owner, state) {
  if (!group || state.processedKingGroups.has(group)) return;
  state.processedKingGroups.add(group);

  const gold = physicalMaterial({
    color: 0xd2a44d,
    emissive: 0x2d1d07,
    emissiveIntensity: 0.34,
    roughness: 0.20,
    metalness: 0.88,
    clearcoat: 0.22,
    envMapIntensity: 1.08,
  });

  // A physical coronet makes Kings recognizable by silhouette, not just glow.
  const coronet = new THREE.Mesh(new THREE.TorusGeometry(0.315, 0.034, 12, 56), gold.clone());
  coronet.rotation.x = Math.PI / 2;
  coronet.position.y = 0.255;
  coronet.castShadow = true;
  group.add(coronet);

  for (let i = 0; i < 6; i += 1) {
    const angle = (i / 6) * Math.PI * 2;
    const point = new THREE.Mesh(new THREE.ConeGeometry(0.045, 0.13, 12), gold.clone());
    point.position.set(Math.cos(angle) * 0.255, 0.335, Math.sin(angle) * 0.255);
    point.castShadow = true;
    group.add(point);
  }

  const topBand = new THREE.Mesh(
    new THREE.CylinderGeometry(0.285, 0.315, 0.055, 48),
    physicalMaterial({
      color: owner === 'W' ? 0xe7decd : 0x1a2029,
      roughness: 0.24,
      metalness: owner === 'W' ? 0.10 : 0.30,
      clearcoat: 0.55,
      clearcoatRoughness: 0.18,
      envMapIntensity: 0.80,
    })
  );
  topBand.position.y = 0.205;
  topBand.castShadow = true;
  group.add(topBand);
  gold.dispose();
}

function enhancePieceBody(body, state) {
  if (state.processedMeshes.has(body)) return;
  const params = body.geometry?.parameters;
  if (body.userData?.kind !== 'piece' || body.geometry?.type !== 'CylinderGeometry') return;
  if (!params || Number(params.height || 0) < 0.20) return;

  const owner = body.userData.owner;
  const king = Number(params.height) >= 0.28;
  const points = checkerProfile(king).map(([radius, y]) => new THREE.Vector2(radius, y));
  replaceGeometry(body, new THREE.LatheGeometry(points, 64));
  body.geometry.computeVertexNormals();

  replaceMaterial(body, physicalMaterial({
    color: owner === 'W' ? 0xeee5d4 : 0x12171e,
    emissive: king ? 0x201607 : 0x000000,
    emissiveIntensity: king ? 0.20 : 0,
    roughness: owner === 'W' ? 0.28 : 0.24,
    metalness: owner === 'W' ? 0.06 : 0.18,
    clearcoat: owner === 'W' ? 0.42 : 0.52,
    clearcoatRoughness: 0.20,
    envMapIntensity: owner === 'W' ? 0.72 : 0.82,
  }));
  body.castShadow = true;
  body.receiveShadow = true;
  addPieceGrooves(body, owner, state);
  if (king) enhanceKingGroup(body.parent, owner, state);
  state.processedMeshes.add(body);
}

function enhancePieceLabel(label, state) {
  if (state.processedMeshes.has(label)) return;
  if (label.userData?.kind !== 'piece' || label.geometry?.type !== 'CircleGeometry') return;

  // The lathed body has a true top surface. Lift the existing authoritative
  // number texture slightly so it stays crisp instead of becoming coplanar.
  label.position.y += 0.018;
  label.renderOrder = 4;
  state.processedMeshes.add(label);
}

function enhanceExistingKingMetal(object, state) {
  if (state.processedMeshes.has(object)) return;
  if (!object.isMesh || object.geometry?.type !== 'TorusGeometry') return;
  const parent = object.parent;
  if (!parent?.children?.some((child) => child.userData?.kind === 'piece')) return;

  replaceMaterial(object, physicalMaterial({
    color: 0xd7a94f,
    emissive: 0x342208,
    emissiveIntensity: 0.42,
    roughness: 0.18,
    metalness: 0.90,
    clearcoat: 0.24,
    envMapIntensity: 1.10,
  }));
  state.processedMeshes.add(object);
}

function enhanceBoardInset(object, state) {
  if (state.processedMeshes.has(object) || object.geometry?.type !== 'BoxGeometry') return;
  const width = Number(object.geometry?.parameters?.width || 0);
  if (Math.abs(width - 8.28) > 0.01) return;
  replaceGeometry(object, new RoundedBoxGeometry(8.28, 0.09, 8.28, 4, 0.075));
  replaceMaterial(object, physicalMaterial({
    color: 0x181d25,
    roughness: 0.58,
    metalness: 0.05,
    clearcoat: 0.08,
    envMapIntensity: 0.34,
  }));
  object.position.y = -0.045;
  state.processedMeshes.add(object);
}

function enhanceScene(scene, state) {
  const objects = [];
  scene.traverse((object) => objects.push(object));

  for (const object of objects) {
    if (!object.isMesh) continue;

    const width = Number(object.geometry?.parameters?.width || 0);
    if (object.geometry?.type === 'BoxGeometry' && Math.abs(width - 8.82) < 0.01) {
      addPremiumFrame(object, state);
      state.processedMeshes.add(object);
      continue;
    }

    enhanceBoardInset(object, state);
    enhanceTile(object, state);
    enhancePieceBody(object, state);
    enhancePieceLabel(object, state);
    enhanceExistingKingMetal(object, state);
  }
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

  // Bloom is thresholded so ordinary board lighting stays clean. The emissive
  // King and Crownline accents should receive most of the visible response.
  const bloomPass = new UnrealBloomPass(
    new THREE.Vector2(width, height),
    constrainedDevice ? 0.12 : 0.22,
    0.30,
    1.02
  );
  bloomPass.enabled = !prefersReducedMotion || !constrainedDevice;
  composer.addPass(bloomPass);

  const smaaPass = new SMAAPass();
  composer.addPass(smaaPass);

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
    processedMeshes: new WeakSet(),
    processedKingGroups: new WeakSet(),
    decorativeObjects: new WeakSet(),
    frameObjects: [],
  };
  renderer[GRAPHICS_STATE] = state;

  try {
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.toneMapping = THREE.AgXToneMapping;
    renderer.toneMappingExposure = 1.08;
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;

    tuneShadows(scene);
    enhanceScene(scene, state);
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
      premiumTabletop: true,
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
    // main.js recreates board tiles and pieces after every authoritative state
    // update. Enhance only newly-created meshes before rendering that frame.
    enhanceScene(scene, state);
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
