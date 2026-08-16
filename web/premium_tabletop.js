import * as THREE from 'three';

// Premium Tabletop is deliberately independent of the optional post-processing
// stack. It intercepts presentation objects as main.js creates them, so the
// visible board/piece language is guaranteed even if graphics.js cannot load.

const groupAdd = THREE.Group.prototype.add;
const upgraded = new WeakSet();

function physical(options = {}) {
  return new THREE.MeshPhysicalMaterial({
    roughness: 0.35,
    metalness: 0.05,
    clearcoat: 0.2,
    clearcoatRoughness: 0.25,
    envMapIntensity: 0.75,
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

  // Deterministic layered grain: enough surface variation to catch highlights
  // without turning the board surround into a literal wood-photo texture.
  for (let y = 0; y < canvas.height; y += 1) {
    const wave = Math.sin(y * 0.19) * 9 + Math.sin(y * 0.047) * 15;
    ctx.strokeStyle = `rgba(255,255,255,${0.035 + ((y % 7) / 7) * 0.025})`;
    ctx.lineWidth = 1;
    ctx.beginPath();
    for (let x = 0; x <= canvas.width; x += 8) {
      const drift = Math.sin((x + wave * 5) * 0.026 + y * 0.045) * 4;
      if (x === 0) ctx.moveTo(x, y + drift);
      else ctx.lineTo(x, y + drift);
    }
    ctx.stroke();
  }

  for (let i = 0; i < 34; i += 1) {
    const y = (i * 37) % canvas.height;
    const phase = i * 0.73;
    ctx.strokeStyle = 'rgba(30,30,30,0.055)';
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
    roughness: 0.33,
    metalness: 0.02,
    clearcoat: 0.42,
    clearcoatRoughness: 0.22,
    bumpMap: woodBump,
    bumpScale: 0.018,
  }));
  base.position.y = -0.30;

  const wood = physical({
    color: 0x3a2417,
    roughness: 0.29,
    metalness: 0.02,
    clearcoat: 0.52,
    clearcoatRoughness: 0.20,
    bumpMap: woodBump,
    bumpScale: 0.026,
  });
  const brass = physical({
    color: 0xb88b42,
    roughness: 0.24,
    metalness: 0.86,
    clearcoat: 0.12,
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
    return mesh;
  });

  const trim = [
    [8.04, 0.035, 0.055, 0, -3.99],
    [8.04, 0.035, 0.055, 0, 3.99],
    [0.055, 0.035, 8.04, -3.99, 0],
    [0.055, 0.035, 8.04, 3.99, 0],
  ].map(([w, h, d, x, z]) => {
    const mesh = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), brass.clone());
    mesh.position.set(x, 0.13, z);
    mesh.castShadow = true;
    return mesh;
  });

  groupAdd.call(group, ...rails, ...trim);
  wood.dispose();
  brass.dispose();
}

function addCrownBorder(tile) {
  if (tile.userData.premiumCrownBorder) return;
  tile.userData.premiumCrownBorder = true;
  const material = physical({
    color: 0xb9914d,
    roughness: 0.24,
    metalness: 0.82,
    clearcoat: 0.10,
  });
  const y = 0.083;
  const bars = [
    [0.90, 0.022, 0.030, 0, y, -0.43],
    [0.90, 0.022, 0.030, 0, y, 0.43],
    [0.030, 0.022, 0.90, -0.43, y, 0],
    [0.030, 0.022, 0.90, 0.43, y, 0],
  ];
  for (const [w, h, d, x, py, z] of bars) {
    const bar = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), material.clone());
    bar.position.set(x, py, z);
    bar.castShadow = true;
    tile.add(bar);
  }
  material.dispose();
}

function upgradeTile(tile) {
  if (upgraded.has(tile) || tile.userData?.kind !== 'square') return;
  const height = Number(tile.geometry?.parameters?.height || 0.10);
  const crown = height > 0.12;
  const playable = Boolean(tile.userData.playable);

  if (crown) {
    replaceMaterial(tile, physical({
      color: 0x506b86,
      emissive: playable ? 0x101a27 : 0x000000,
      emissiveIntensity: playable ? 0.24 : 0,
      roughness: 0.25,
      metalness: 0.10,
      clearcoat: 0.62,
      clearcoatRoughness: 0.19,
      opacity: playable ? 1 : 0.52,
      transparent: !playable,
    }));
    addCrownBorder(tile);
  } else {
    const original = tile.material?.color?.getHex?.() ?? 0x252c37;
    const dark = original < 0x808080;
    replaceMaterial(tile, physical({
      color: dark ? 0x2a3038 : 0xd8cfbd,
      roughness: dark ? 0.50 : 0.56,
      metalness: 0.02,
      clearcoat: dark ? 0.12 : 0.07,
      clearcoatRoughness: 0.46,
      opacity: playable ? 1 : 0.39,
      transparent: !playable,
    }));
  }
  upgraded.add(tile);
}

function checkerProfile(king) {
  const profile = king
    ? [
        [0, -0.16], [0.31, -0.16], [0.39, -0.14], [0.44, -0.085],
        [0.45, -0.015], [0.43, 0.055], [0.39, 0.10], [0.405, 0.14],
        [0.37, 0.18], [0.315, 0.205], [0, 0.205],
      ]
    : [
        [0, -0.12], [0.31, -0.12], [0.39, -0.10], [0.435, -0.055],
        [0.445, 0], [0.425, 0.055], [0.38, 0.09], [0.31, 0.12], [0, 0.12],
      ];
  return profile.map(([r, y]) => new THREE.Vector2(r, y));
}

function addGrooves(body, owner, king) {
  const material = physical({
    color: owner === 'W' ? 0xc2b18f : 0x4d5868,
    roughness: 0.25,
    metalness: owner === 'W' ? 0.07 : 0.28,
    clearcoat: 0.28,
  });
  const levels = king ? [-0.066, 0.030] : [-0.058, 0.058];
  for (const y of levels) {
    const ring = new THREE.Mesh(new THREE.TorusGeometry(0.397, 0.015, 8, 48), material.clone());
    ring.rotation.x = Math.PI / 2;
    ring.position.y = y;
    body.add(ring);
  }
  material.dispose();
}

function addKingSignet(group, owner) {
  if (group.userData.premiumKingSignet) return;
  group.userData.premiumKingSignet = true;

  const gold = physical({
    color: 0xc99a44,
    emissive: 0x241704,
    emissiveIntensity: 0.16,
    roughness: 0.22,
    metalness: 0.88,
    clearcoat: 0.14,
  });
  const pieceMaterial = physical({
    color: owner === 'W' ? 0xe9ddc7 : 0x151c25,
    roughness: owner === 'W' ? 0.25 : 0.22,
    metalness: owner === 'W' ? 0.05 : 0.19,
    clearcoat: 0.46,
    clearcoatRoughness: 0.18,
  });

  // A King reads as a refined double-stack/signature piece rather than a
  // literal wearable crown. The gold is structural: waist band + top signet.
  const upperDeck = new THREE.Mesh(
    new THREE.CylinderGeometry(0.315, 0.35, 0.065, 56),
    pieceMaterial
  );
  upperDeck.position.y = 0.177;
  upperDeck.castShadow = true;
  upperDeck.receiveShadow = true;

  const waistBand = new THREE.Mesh(new THREE.TorusGeometry(0.405, 0.022, 10, 56), gold.clone());
  waistBand.rotation.x = Math.PI / 2;
  waistBand.position.y = 0.095;
  waistBand.castShadow = true;

  const topBand = new THREE.Mesh(new THREE.TorusGeometry(0.318, 0.018, 10, 56), gold.clone());
  topBand.rotation.x = Math.PI / 2;
  topBand.position.y = 0.210;
  topBand.castShadow = true;

  const signet = new THREE.Mesh(
    new THREE.RingGeometry(0.248, 0.307, 64),
    gold.clone()
  );
  signet.rotation.x = -Math.PI / 2;
  signet.position.y = 0.218;
  signet.renderOrder = 3;

  groupAdd.call(group, upperDeck, waistBand, topBand, signet);
  gold.dispose();
}

function suppressLegacyKingTreatment(group, object) {
  if (!group.userData.premiumKingSignet || !object?.isMesh) return;

  // main.js still creates its original crown-cap/ring/halo for semantic visual
  // feedback. Keep a faint halo, but suppress the literal crown geometry so the
  // Premium Tabletop signet remains the King silhouette.
  if (object.geometry?.type === 'RingGeometry' && object.userData?.pulse) {
    if (object.material) object.material.opacity = Math.min(object.material.opacity ?? 1, 0.10);
    return;
  }
  if (object.geometry?.type === 'TorusGeometry') {
    object.visible = false;
    return;
  }
  if (
    object.geometry?.type === 'CylinderGeometry' &&
    Number(object.geometry?.parameters?.height || 1) <= 0.10
  ) {
    object.visible = false;
  }
}

function upgradePiece(group, body) {
  if (upgraded.has(body) || body.userData?.kind !== 'piece') return;
  if (body.geometry?.type !== 'CylinderGeometry') return;
  const height = Number(body.geometry?.parameters?.height || 0);
  if (height < 0.20) return;

  const owner = body.userData.owner;
  const king = height >= 0.28;
  replaceGeometry(body, new THREE.LatheGeometry(checkerProfile(king), 64));
  body.geometry.computeVertexNormals();
  replaceMaterial(body, physical({
    color: owner === 'W' ? 0xf0e5cf : 0x11171f,
    emissive: king ? 0x171005 : 0x000000,
    emissiveIntensity: king ? 0.09 : 0,
    roughness: owner === 'W' ? 0.29 : 0.24,
    metalness: owner === 'W' ? 0.04 : 0.16,
    clearcoat: owner === 'W' ? 0.38 : 0.48,
    clearcoatRoughness: 0.20,
  }));
  addGrooves(body, owner, king);
  if (king) addKingSignet(group, owner);
  upgraded.add(body);
}

function upgradeLabel(label) {
  if (upgraded.has(label) || label.userData?.kind !== 'piece') return;
  if (label.geometry?.type !== 'CircleGeometry') return;
  label.position.y += 0.030;
  label.renderOrder = 4;
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
  version: 3,
  kingDesign: 'signet',
  woodSurface: true,
};
