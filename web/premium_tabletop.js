import * as THREE from 'three';

// Premium Tabletop is deliberately independent of the optional post-processing
// stack. It intercepts presentation objects as main.js creates them, so the
// visible board/piece language is guaranteed even if graphics.js cannot load.

const groupAdd = THREE.Group.prototype.add;
const upgraded = new WeakSet();

function physical(options = {}) {
  return new THREE.MeshPhysicalMaterial({
    roughness: 0.50,
    metalness: 0.02,
    clearcoat: 0.08,
    clearcoatRoughness: 0.62,
    envMapIntensity: 0.30,
    ...options,
  });
}

function replaceMaterial(mesh, material) {
  mesh.material?.dispose?.();
  mesh.material = material;
}

function replaceGeometry(mesh, geometry) {
  mesh.geometry?.dispose?.();
  mesh.geometry = geometry;
}

function woodBumpTexture() {
  const canvas = document.createElement('canvas');
  canvas.width = 512;
  canvas.height = 128;
  const ctx = canvas.getContext('2d');
  ctx.fillStyle = '#808080';
  ctx.fillRect(0, 0, canvas.width, canvas.height);

  // Deterministic micro-grain. It should only become visible when light grazes
  // the frame; the board should never read as a photo-textured slab.
  for (let y = 0; y < canvas.height; y += 1) {
    const wave = Math.sin(y * 0.19) * 9 + Math.sin(y * 0.047) * 15;
    ctx.strokeStyle = `rgba(255,255,255,${0.022 + ((y % 7) / 7) * 0.014})`;
    ctx.lineWidth = 1;
    ctx.beginPath();
    for (let x = 0; x <= canvas.width; x += 8) {
      const drift = Math.sin((x + wave * 5) * 0.026 + y * 0.045) * 4;
      if (x === 0) ctx.moveTo(x, y + drift);
      else ctx.lineTo(x, y + drift);
    }
    ctx.stroke();
  }

  for (let i = 0; i < 30; i += 1) {
    const y = (i * 37) % canvas.height;
    const phase = i * 0.73;
    ctx.strokeStyle = 'rgba(30,30,30,0.035)';
    ctx.lineWidth = i % 5 === 0 ? 2 : 1;
    ctx.beginPath();
    for (let x = 0; x <= canvas.width; x += 6) {
      const py = y + Math.sin(x * 0.02 + phase) * (2 + (i % 3));
      if (x === 0) ctx.moveTo(x, py);
      else ctx.lineTo(x, py);
    }
    ctx.stroke();
  }

  const texture = new THREE.CanvasTexture(canvas);
  texture.wrapS = THREE.RepeatWrapping;
  texture.wrapT = THREE.RepeatWrapping;
  texture.repeat.set(3.2, 1.25);
  texture.needsUpdate = true;
  return texture;
}

const woodBump = woodBumpTexture();

function addFrame(group, base) {
  if (group.userData.premiumTabletopFrame) return;
  group.userData.premiumTabletopFrame = true;

  replaceMaterial(base, physical({
    color: 0x24170f,
    roughness: 0.66,
    metalness: 0.01,
    clearcoat: 0.08,
    clearcoatRoughness: 0.72,
    envMapIntensity: 0.16,
    bumpMap: woodBump,
    bumpScale: 0.012,
  }));
  base.position.y = -0.30;

  const wood = physical({
    color: 0x3a2417,
    roughness: 0.61,
    metalness: 0.01,
    clearcoat: 0.10,
    clearcoatRoughness: 0.68,
    envMapIntensity: 0.18,
    bumpMap: woodBump,
    bumpScale: 0.016,
  });
  const brass = physical({
    color: 0xaa8244,
    roughness: 0.44,
    metalness: 0.82,
    clearcoat: 0.04,
    clearcoatRoughness: 0.58,
    envMapIntensity: 0.26,
  });

  const rails = [
    [8.58, 0.26, 0.36, 0, -4.17],
    [8.58, 0.26, 0.36, 0, 4.17],
    [0.36, 0.26, 8.58, -4.17, 0],
    [0.36, 0.26, 8.58, 4.17, 0],
  ].map(([w, h, d, x, z]) => {
    const mesh = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), wood.clone());
    mesh.position.set(x, -0.015, z);
    mesh.castShadow = true;
    mesh.receiveShadow = true;
    mesh.userData.premiumManaged = true;
    return mesh;
  });

  const trim = [
    [8.04, 0.035, 0.050, 0, -3.99],
    [8.04, 0.035, 0.050, 0, 3.99],
    [0.050, 0.035, 8.04, -3.99, 0],
    [0.050, 0.035, 8.04, 3.99, 0],
  ].map(([w, h, d, x, z]) => {
    const mesh = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), brass.clone());
    mesh.position.set(x, 0.13, z);
    mesh.castShadow = true;
    mesh.userData.premiumManaged = true;
    return mesh;
  });

  base.userData.premiumManaged = true;
  groupAdd.call(group, ...rails, ...trim);
  wood.dispose();
  brass.dispose();
}

function addCrownBorder(tile) {
  if (tile.userData.premiumCrownBorder) return;
  tile.userData.premiumCrownBorder = true;
  const material = physical({
    color: 0xad8c55,
    roughness: 0.46,
    metalness: 0.78,
    clearcoat: 0.03,
    clearcoatRoughness: 0.62,
    envMapIntensity: 0.24,
  });
  const y = 0.083;
  const bars = [
    [0.90, 0.020, 0.026, 0, y, -0.43],
    [0.90, 0.020, 0.026, 0, y, 0.43],
    [0.026, 0.020, 0.90, -0.43, y, 0],
    [0.026, 0.020, 0.90, 0.43, y, 0],
  ];
  for (const [w, h, d, x, py, z] of bars) {
    const bar = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), material.clone());
    bar.position.set(x, py, z);
    bar.castShadow = true;
    bar.userData.premiumManaged = true;
    tile.add(bar);
  }
  material.dispose();
}

function upgradeTile(tile) {
  if (upgraded.has(tile) || tile.userData?.kind !== 'square') return;
  const height = Number(tile.geometry?.parameters?.height || 0.10);
  const crown = height > 0.12;
  const playable = Boolean(tile.userData.playable);

  // Convert the source box into a generic BufferGeometry after reading its
  // dimensions. This keeps the optional graphics.js fallback from re-styling
  // Premium Tabletop tiles with its older, glossier material pass.
  const stableGeometry = new THREE.BufferGeometry().copy(tile.geometry);
  stableGeometry.type = 'CrownlinePremiumTileGeometry';
  replaceGeometry(tile, stableGeometry);
  tile.userData.premiumManaged = true;

  if (crown) {
    replaceMaterial(tile, physical({
      color: 0x506b86,
      emissive: playable ? 0x101a27 : 0x000000,
      emissiveIntensity: playable ? 0.20 : 0,
      roughness: 0.40,
      metalness: 0.06,
      clearcoat: 0.22,
      clearcoatRoughness: 0.55,
      envMapIntensity: 0.28,
      opacity: playable ? 1 : 0.52,
      transparent: !playable,
    }));
    addCrownBorder(tile);
  } else {
    const original = tile.material?.color?.getHex?.() ?? 0x252c37;
    const dark = original < 0x808080;
    replaceMaterial(tile, physical({
      color: dark ? 0x2a3038 : 0xd8cfbd,
      roughness: dark ? 0.58 : 0.62,
      metalness: 0.01,
      clearcoat: dark ? 0.05 : 0.03,
      clearcoatRoughness: 0.70,
      envMapIntensity: dark ? 0.18 : 0.16,
      opacity: playable ? 1 : 0.39,
      transparent: !playable,
    }));
  }
  upgraded.add(tile);
}

function ribbedCheckerGeometry({
  radius = 0.435,
  height = 0.24,
  ribs = 20,
  ribDepth = 0.010,
  upper = false,
} = {}) {
  const radialSegments = 96;
  const heightSegments = upper ? 5 : 8;
  const geometry = new THREE.CylinderGeometry(radius, radius, height, radialSegments, heightSegments, false);
  const position = geometry.attributes.position;
  const half = height / 2;
  const v = new THREE.Vector3();

  for (let i = 0; i < position.count; i += 1) {
    v.fromBufferAttribute(position, i);
    const r = Math.hypot(v.x, v.z);
    if (r < 0.0001) continue;

    const t = THREE.MathUtils.clamp((v.y + half) / height, 0, 1);
    const angle = Math.atan2(v.z, v.x);

    // Traditional checker language: broad foot, gently stepped sidewall,
    // narrower top deck. Keep the changes small enough to stay elegant.
    let shape = 1;
    if (t < 0.12) shape = 1.00;
    else if (t < 0.24) shape = THREE.MathUtils.lerp(1.00, 0.955, (t - 0.12) / 0.12);
    else if (t < 0.68) shape = upper ? 0.955 : 0.950;
    else if (t < 0.84) shape = THREE.MathUtils.lerp(0.950, upper ? 0.900 : 0.885, (t - 0.68) / 0.16);
    else shape = upper ? 0.900 : 0.885;

    // Fine vertical ribs live mostly on the sidewall. They are shallow grooves,
    // not gear teeth; at normal board scale they should read as grip texture.
    const ribWindow = t > 0.16 && t < 0.78 ? Math.sin(((t - 0.16) / 0.62) * Math.PI) : 0;
    const groove = ribDepth * ribWindow * (0.5 + 0.5 * Math.cos(ribs * angle));
    const targetRadius = Math.max(0.001, radius * shape - groove);
    const scale = targetRadius / r;
    v.x *= scale;
    v.z *= scale;

    position.setXYZ(i, v.x, v.y, v.z);
  }

  position.needsUpdate = true;
  geometry.computeVertexNormals();
  geometry.type = upper ? 'CrownlineRibbedUpperGeometry' : 'CrownlineRibbedCheckerGeometry';
  return geometry;
}

function pieceMaterial(owner, king = false) {
  return physical({
    color: owner === 'W' ? 0xefe5d2 : 0x151a20,
    emissive: king ? 0x100b03 : 0x000000,
    emissiveIntensity: king ? 0.035 : 0,
    roughness: owner === 'W' ? 0.48 : 0.42,
    metalness: 0.01,
    clearcoat: king ? 0.13 : 0.10,
    clearcoatRoughness: king ? 0.60 : 0.66,
    envMapIntensity: king ? 0.25 : 0.21,
  });
}

function addTopInset(body, owner, king) {
  const insetMaterial = physical({
    color: owner === 'W' ? 0xd7c8aa : 0x303944,
    roughness: 0.52,
    metalness: 0.02,
    clearcoat: 0.05,
    clearcoatRoughness: 0.70,
    envMapIntensity: 0.18,
  });
  const ring = new THREE.Mesh(
    new THREE.TorusGeometry(king ? 0.315 : 0.325, 0.010, 8, 56),
    insetMaterial
  );
  ring.rotation.x = Math.PI / 2;
  ring.position.y = king ? 0.136 : 0.122;
  ring.userData.premiumManaged = true;
  body.add(ring);
}

function addKingStack(group, owner) {
  if (group.userData.premiumKingStack) return;
  group.userData.premiumKingStack = true;

  const upperDeck = new THREE.Mesh(
    ribbedCheckerGeometry({ radius: 0.365, height: 0.105, ribs: 20, ribDepth: 0.007, upper: true }),
    pieceMaterial(owner, true)
  );
  upperDeck.position.y = 0.165;
  upperDeck.castShadow = true;
  upperDeck.receiveShadow = true;
  upperDeck.userData.premiumManaged = true;

  const gold = physical({
    color: 0xb78b43,
    emissive: 0x160f03,
    emissiveIntensity: 0.055,
    roughness: 0.46,
    metalness: 0.80,
    clearcoat: 0.04,
    clearcoatRoughness: 0.58,
    envMapIntensity: 0.27,
  });

  const waistBand = new THREE.Mesh(new THREE.TorusGeometry(0.386, 0.018, 10, 56), gold.clone());
  waistBand.geometry.type = 'CrownlineKingBandGeometry';
  waistBand.rotation.x = Math.PI / 2;
  waistBand.position.y = 0.111;
  waistBand.castShadow = true;
  waistBand.userData.premiumManaged = true;

  const signet = new THREE.Mesh(new THREE.RingGeometry(0.248, 0.302, 64), gold.clone());
  signet.rotation.x = -Math.PI / 2;
  signet.position.y = 0.221;
  signet.renderOrder = 3;
  signet.userData.premiumManaged = true;

  groupAdd.call(group, upperDeck, waistBand, signet);
  gold.dispose();
}

function suppressLegacyKingTreatment(group, object) {
  if (!group.userData.premiumKingStack || !object?.isMesh) return;

  // main.js still creates its original crown-cap/ring/halo. Retain only a very
  // faint halo for promotion/state feedback; the physical King is a double-stack
  // ribbed checker, not a piece wearing a crown.
  if (object.geometry?.type === 'RingGeometry' && object.userData?.pulse) {
    if (object.material) object.material.opacity = Math.min(object.material.opacity ?? 1, 0.075);
    object.userData.premiumManaged = true;
    return;
  }
  if (object.geometry?.type === 'TorusGeometry') {
    object.visible = false;
    object.userData.premiumManaged = true;
    return;
  }
  if (
    object.geometry?.type === 'CylinderGeometry' &&
    Number(object.geometry?.parameters?.height || 1) <= 0.10
  ) {
    object.visible = false;
    object.userData.premiumManaged = true;
  }
}

function upgradePiece(group, body) {
  if (upgraded.has(body) || body.userData?.kind !== 'piece') return;
  if (body.geometry?.type !== 'CylinderGeometry') return;
  const sourceHeight = Number(body.geometry?.parameters?.height || 0);
  if (sourceHeight < 0.20) return;

  const owner = body.userData.owner;
  const king = sourceHeight >= 0.28;
  replaceGeometry(body, ribbedCheckerGeometry({
    radius: king ? 0.445 : 0.435,
    height: king ? 0.285 : 0.235,
    ribs: 20,
    ribDepth: king ? 0.010 : 0.009,
  }));
  replaceMaterial(body, pieceMaterial(owner, king));
  body.castShadow = true;
  body.receiveShadow = true;
  body.userData.premiumManaged = true;
  addTopInset(body, owner, king);
  if (king) addKingStack(group, owner);
  upgraded.add(body);
}

function upgradeLabel(label) {
  if (upgraded.has(label) || label.userData?.kind !== 'piece') return;
  if (label.geometry?.type !== 'CircleGeometry') return;
  label.position.y += 0.012;
  label.renderOrder = 4;
  label.userData.premiumManaged = true;
  upgraded.add(label);
}

THREE.Group.prototype.add = function crownlinePremiumAdd(...objects) {
  for (const object of objects) {
    if (!object?.isMesh) continue;

    suppressLegacyKingTreatment(this, object);

    const width = Number(object.geometry?.parameters?.width || 0);
    if (object.geometry?.type === 'BoxGeometry' && Math.abs(width - 8.82) < 0.01) {
      addFrame(this, object);
    }
    if (object.userData?.kind === 'square') upgradeTile(object);
    if (object.userData?.kind === 'piece') {
      upgradePiece(this, object);
      upgradeLabel(object);
    }
  }
  return groupAdd.apply(this, objects);
};

window.CrownlinePremiumTabletop = {
  active: true,
  architecture: 'scene-construction',
  version: 4,
  pieceDesign: 'ribbed-checker',
  kingDesign: 'double-stack-signet',
  finish: 'satin',
  woodSurface: true,
};
