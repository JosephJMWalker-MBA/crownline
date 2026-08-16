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

function addFrame(group, base) {
  if (group.userData.premiumTabletopFrame) return;
  group.userData.premiumTabletopFrame = true;

  replaceMaterial(base, physical({
    color: 0x2b1c12,
    roughness: 0.30,
    metalness: 0.02,
    clearcoat: 0.48,
    clearcoatRoughness: 0.20,
  }));
  base.position.y = -0.30;

  const wood = physical({
    color: 0x3a2417,
    roughness: 0.27,
    metalness: 0.02,
    clearcoat: 0.58,
    clearcoatRoughness: 0.18,
  });
  const brass = physical({
    color: 0xc1964d,
    roughness: 0.21,
    metalness: 0.86,
    clearcoat: 0.16,
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
    color: 0xc1964d,
    roughness: 0.20,
    metalness: 0.88,
    clearcoat: 0.14,
  });
  const y = 0.083;
  const bars = [
    [0.90, 0.022, 0.035, 0, y, -0.43],
    [0.90, 0.022, 0.035, 0, y, 0.43],
    [0.035, 0.022, 0.90, -0.43, y, 0],
    [0.035, 0.022, 0.90, 0.43, y, 0],
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
      color: 0x506d8b,
      emissive: playable ? 0x101c2a : 0x000000,
      emissiveIntensity: playable ? 0.28 : 0,
      roughness: 0.22,
      metalness: 0.11,
      clearcoat: 0.72,
      clearcoatRoughness: 0.16,
      opacity: playable ? 1 : 0.52,
      transparent: !playable,
    }));
    addCrownBorder(tile);
  } else {
    const original = tile.material?.color?.getHex?.() ?? 0x252c37;
    const dark = original < 0x808080;
    replaceMaterial(tile, physical({
      color: dark ? 0x2b3139 : 0xd8cfbd,
      roughness: dark ? 0.48 : 0.54,
      metalness: 0.02,
      clearcoat: dark ? 0.16 : 0.10,
      clearcoatRoughness: 0.42,
      opacity: playable ? 1 : 0.39,
      transparent: !playable,
    }));
  }
  upgraded.add(tile);
}

function checkerProfile(king) {
  const profile = king
    ? [[0, -0.16], [0.31, -0.16], [0.39, -0.14], [0.44, -0.08], [0.45, 0], [0.42, 0.08], [0.38, 0.12], [0.40, 0.16], [0.35, 0.20], [0.29, 0.21], [0, 0.21]]
    : [[0, -0.12], [0.31, -0.12], [0.39, -0.10], [0.435, -0.055], [0.445, 0], [0.425, 0.055], [0.38, 0.09], [0.31, 0.12], [0, 0.12]];
  return profile.map(([r, y]) => new THREE.Vector2(r, y));
}

function addGrooves(body, owner) {
  const material = physical({
    color: owner === 'W' ? 0xc9baa0 : 0x46505e,
    roughness: 0.22,
    metalness: owner === 'W' ? 0.08 : 0.32,
    clearcoat: 0.35,
  });
  for (const y of [-0.058, 0.058]) {
    const ring = new THREE.Mesh(new THREE.TorusGeometry(0.397, 0.014, 8, 48), material.clone());
    ring.rotation.x = Math.PI / 2;
    ring.position.y = y;
    body.add(ring);
  }
  material.dispose();
}

function addCoronet(group, owner) {
  if (group.userData.premiumCoronet) return;
  group.userData.premiumCoronet = true;
  const gold = physical({
    color: 0xd9a94e,
    emissive: 0x352208,
    emissiveIntensity: 0.32,
    roughness: 0.18,
    metalness: 0.90,
    clearcoat: 0.20,
  });

  const collar = new THREE.Mesh(new THREE.TorusGeometry(0.325, 0.038, 12, 56), gold.clone());
  collar.rotation.x = Math.PI / 2;
  collar.position.y = 0.265;
  collar.castShadow = true;
  groupAdd.call(group, collar);

  for (let i = 0; i < 6; i += 1) {
    const angle = (i / 6) * Math.PI * 2;
    const point = new THREE.Mesh(new THREE.ConeGeometry(0.052, 0.15, 12), gold.clone());
    point.position.set(Math.cos(angle) * 0.27, 0.35, Math.sin(angle) * 0.27);
    point.castShadow = true;
    groupAdd.call(group, point);
  }

  const crownDeck = new THREE.Mesh(
    new THREE.CylinderGeometry(0.29, 0.32, 0.06, 48),
    physical({
      color: owner === 'W' ? 0xe8deca : 0x1b222c,
      roughness: 0.24,
      metalness: owner === 'W' ? 0.08 : 0.28,
      clearcoat: 0.50,
    })
  );
  crownDeck.position.y = 0.21;
  crownDeck.castShadow = true;
  groupAdd.call(group, crownDeck);
  gold.dispose();
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
    emissive: king ? 0x201607 : 0x000000,
    emissiveIntensity: king ? 0.18 : 0,
    roughness: owner === 'W' ? 0.27 : 0.23,
    metalness: owner === 'W' ? 0.05 : 0.17,
    clearcoat: owner === 'W' ? 0.42 : 0.54,
    clearcoatRoughness: 0.18,
  }));
  addGrooves(body, owner);
  if (king) addCoronet(group, owner);
  upgraded.add(body);
}

function upgradeLabel(label) {
  if (upgraded.has(label) || label.userData?.kind !== 'piece') return;
  if (label.geometry?.type !== 'CircleGeometry') return;
  label.position.y += 0.028;
  label.renderOrder = 4;
  upgraded.add(label);
}

THREE.Group.prototype.add = function crownlinePremiumAdd(...objects) {
  for (const object of objects) {
    if (!object?.isMesh) continue;
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
  version: 2,
};
