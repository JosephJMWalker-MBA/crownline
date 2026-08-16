import * as THREE from 'three';

const canvas = document.querySelector('#board');
const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
renderer.outputColorSpace = THREE.SRGBColorSpace;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.05;
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;

const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(38, 1, 0.1, 100);
camera.position.set(7.7, 9.8, 10.8);
camera.lookAt(0, 0, 0);

scene.add(new THREE.HemisphereLight(0xdde7ff, 0x161a22, 1.9));
const key = new THREE.DirectionalLight(0xffffff, 4.1);
key.position.set(4, 10, 6);
key.castShadow = true;
key.shadow.mapSize.set(2048, 2048);
key.shadow.camera.left = -8;
key.shadow.camera.right = 8;
key.shadow.camera.top = 8;
key.shadow.camera.bottom = -8;
scene.add(key);

const rim = new THREE.DirectionalLight(0x8fb6ff, 1.15);
rim.position.set(-7, 5, -6);
scene.add(rim);

const floor = new THREE.Mesh(
  new THREE.PlaneGeometry(30, 30),
  new THREE.MeshStandardMaterial({ color: 0x080b10, roughness: 0.96, metalness: 0.02 })
);
floor.rotation.x = -Math.PI / 2;
floor.position.y = -0.47;
floor.receiveShadow = true;
scene.add(floor);

const boardGroup = new THREE.Group();
scene.add(boardGroup);

const boardBase = new THREE.Mesh(
  new THREE.BoxGeometry(8.82, 0.38, 8.82),
  new THREE.MeshStandardMaterial({ color: 0x141a24, roughness: 0.55, metalness: 0.18 })
);
boardBase.position.y = -0.27;
boardBase.receiveShadow = true;
boardBase.castShadow = true;
boardGroup.add(boardBase);

const inset = new THREE.Mesh(
  new THREE.BoxGeometry(8.28, 0.08, 8.28),
  new THREE.MeshStandardMaterial({ color: 0x202631, roughness: 0.62, metalness: 0.08 })
);
inset.position.y = -0.045;
inset.receiveShadow = true;
boardGroup.add(inset);

const ui = {
  game: document.querySelector('#game-label'),
  turn: document.querySelector('#turn-label'),
  variant: document.querySelector('#variant-label'),
  scoreA: document.querySelector('#score-a'),
  scoreB: document.querySelector('#score-b'),
  scoreCardA: document.querySelector('#score-card-a'),
  scoreCardB: document.querySelector('#score-card-b'),
  bankW: document.querySelector('#bank-w'),
  bankB: document.querySelector('#bank-b'),
  meldW: document.querySelector('#meld-w'),
  meldB: document.querySelector('#meld-b'),
  moves: document.querySelector('#moves'),
  status: document.querySelector('#status'),
  advance: document.querySelector('#advance'),
  reset: document.querySelector('#reset'),
  opponent: document.querySelector('#opponent-mode'),
  flip: document.querySelector('#flip-board'),
  eventBanner: document.querySelector('#event-banner'),
  transition: document.querySelector('#game-transition'),
  transitionTitle: document.querySelector('#transition-title'),
  transitionSub: document.querySelector('#transition-sub'),
  meldDialog: document.querySelector('#meld-dialog'),
  meldOptions: document.querySelector('#meld-options'),
  meldCancel: document.querySelector('#meld-cancel'),
  routeDialog: document.querySelector('#route-dialog'),
  routeOptions: document.querySelector('#route-options'),
  routeCancel: document.querySelector('#route-cancel'),
};

let state = null;
let pendingMove = null;
let selectedSquare = null;
let computerBusy = false;
let animationBusy = false;
let statusOverride = null;
let eventSerial = 0;

const dynamicObjects = [];
const clickTargets = [];
const highlightObjects = [];
const effectObjects = [];
const previewObjects = [];
const previewTileBases = [];
const pieceGroups = new Map();
const tileObjects = new Map();
const raycaster = new THREE.Raycaster();
const pointer = new THREE.Vector2();

let boardRotation = 0;
let targetBoardRotation = 0;
let pointerDown = false;
let draggingBoard = false;
let dragStartX = 0;
let dragStartY = 0;
let dragLastX = 0;
let pressEvent = null;

ui.opponent.value = localStorage.getItem('crownline-opponent') || 'human';
const savedRotation = Number(localStorage.getItem('crownline-board-rotation'));
if (Number.isFinite(savedRotation)) {
  boardRotation = savedRotation;
  targetBoardRotation = savedRotation;
  boardGroup.rotation.y = savedRotation;
}

function squareToWorld(square) {
  const file = square.charCodeAt(0) - 97;
  const rank = Number(square[1]) - 1;
  return { x: file - 3.5, z: 3.5 - rank };
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function tween(duration, update) {
  return new Promise((resolve) => {
    const start = performance.now();
    const frame = (now) => {
      const raw = Math.min(1, (now - start) / duration);
      const t = raw < 0.5 ? 2 * raw * raw : 1 - Math.pow(-2 * raw + 2, 2) / 2;
      update(t, raw);
      if (raw < 1) requestAnimationFrame(frame);
      else resolve();
    };
    requestAnimationFrame(frame);
  });
}

function disposeObject(object) {
  object.traverse?.((child) => {
    child.geometry?.dispose?.();
    if (Array.isArray(child.material)) child.material.forEach((m) => m.dispose?.());
    else child.material?.dispose?.();
    child.material?.map?.dispose?.();
  });
}

function clearObjects(list) {
  while (list.length) {
    const object = list.pop();
    boardGroup.remove(object);
    disposeObject(object);
  }
}

function clearEffects() {
  clearObjects(effectObjects);
}

function clearCrownlinePreview() {
  while (previewTileBases.length) {
    const entry = previewTileBases.pop();
    if (!entry?.tile?.material) continue;
    entry.tile.material.emissive.copy(entry.emissive);
    entry.tile.material.emissiveIntensity = entry.intensity;
  }
  clearObjects(previewObjects);
}

function showCrownlinePreview(line) {
  clearCrownlinePreview();
  if (!Array.isArray(line) || line.length !== 3) return;

  const positions = line.map((square) => {
    const p = squareToWorld(square);
    return new THREE.Vector3(p.x, 0.35, p.z);
  });
  const geometry = new THREE.BufferGeometry().setFromPoints(positions);
  const material = new THREE.LineBasicMaterial({
    color: 0xf0c86a,
    transparent: true,
    opacity: 0.92,
  });
  const beam = new THREE.Line(geometry, material);
  boardGroup.add(beam);
  previewObjects.push(beam);

  for (const square of line) {
    const p = squareToWorld(square);
    const ring = new THREE.Mesh(
      new THREE.RingGeometry(0.31, 0.50, 48),
      new THREE.MeshBasicMaterial({
        color: 0xf0c86a,
        transparent: true,
        opacity: 0.78,
        blending: THREE.AdditiveBlending,
        side: THREE.DoubleSide,
        depthWrite: false,
      })
    );
    ring.rotation.x = -Math.PI / 2;
    ring.position.set(p.x, 0.27, p.z);
    boardGroup.add(ring);
    previewObjects.push(ring);

    const tile = tileObjects.get(square);
    if (tile?.material?.emissive) {
      previewTileBases.push({
        tile,
        emissive: tile.material.emissive.clone(),
        intensity: tile.material.emissiveIntensity || 0,
      });
      tile.material.emissive.setHex(0xb98a24);
      tile.material.emissiveIntensity = 1.2;
    }
  }
}

window.addEventListener('crownline-preview-line', (event) => {
  const line = event.detail?.line;
  if (Array.isArray(line) && line.length === 3) showCrownlinePreview(line);
  else clearCrownlinePreview();
});

function clearDynamic() {
  clearHighlights();
  clearEffects();
  clearCrownlinePreview();
  clearObjects(dynamicObjects);
  clickTargets.length = 0;
  pieceGroups.clear();
  tileObjects.clear();
}

function clearHighlights() {
  clearObjects(highlightObjects);
}

function pieceLabelTexture(piece) {
  const canvas2d = document.createElement('canvas');
  canvas2d.width = 256;
  canvas2d.height = 256;
  const ctx = canvas2d.getContext('2d');
  ctx.clearRect(0, 0, 256, 256);
  ctx.fillStyle = piece.owner === 'W' ? '#111820' : '#f3f5f8';
  ctx.font = '800 112px system-ui';
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  ctx.fillText(String(piece.value), 128, 132);
  if (piece.king) {
    ctx.fillStyle = '#d7ad55';
    ctx.font = '900 38px system-ui';
    ctx.fillText('K', 128, 44);
  }
  const texture = new THREE.CanvasTexture(canvas2d);
  texture.colorSpace = THREE.SRGBColorSpace;
  return texture;
}

function squareMarkTexture(square, crown, darkSquare, playable) {
  const label = document.createElement('canvas');
  label.width = 256;
  label.height = 256;
  const ctx = label.getContext('2d');
  ctx.clearRect(0, 0, 256, 256);

  const lightText = crown !== undefined || darkSquare;
  ctx.fillStyle = lightText ? 'rgba(244,247,251,.72)' : 'rgba(22,26,33,.58)';
  ctx.font = '700 27px system-ui';
  ctx.textAlign = 'left';
  ctx.textBaseline = 'bottom';
  ctx.fillText(square, 18, 238);

  if (crown !== undefined) {
    ctx.fillStyle = playable ? '#f6f8fb' : 'rgba(246,248,251,.45)';
    ctx.font = '850 100px system-ui';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText(String(crown), 128, 124);
  }

  const texture = new THREE.CanvasTexture(label);
  texture.colorSpace = THREE.SRGBColorSpace;
  texture.anisotropy = Math.min(8, renderer.capabilities.getMaxAnisotropy());
  return texture;
}

function addKingTreatment(group, piece) {
  const gold = 0xd8ad55;
  const halo = new THREE.Mesh(
    new THREE.RingGeometry(0.39, 0.66, 64),
    new THREE.MeshBasicMaterial({
      color: gold,
      transparent: true,
      opacity: 0.23,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
      side: THREE.DoubleSide,
    })
  );
  halo.rotation.x = -Math.PI / 2;
  halo.position.y = -0.145;
  halo.userData.pulse = true;
  group.add(halo);

  const crownRing = new THREE.Mesh(
    new THREE.TorusGeometry(0.30, 0.035, 12, 48),
    new THREE.MeshStandardMaterial({
      color: 0xe1bc69,
      emissive: 0x6b4e18,
      emissiveIntensity: 1.35,
      roughness: 0.28,
      metalness: 0.72,
    })
  );
  crownRing.rotation.x = Math.PI / 2;
  crownRing.position.y = 0.145;
  crownRing.castShadow = true;
  group.add(crownRing);

  const crownCap = new THREE.Mesh(
    new THREE.CylinderGeometry(0.27, 0.30, 0.075, 48),
    new THREE.MeshStandardMaterial({
      color: piece.owner === 'W' ? 0xf3eee2 : 0x242933,
      emissive: 0x3a2b0f,
      emissiveIntensity: 0.45,
      roughness: 0.34,
      metalness: 0.38,
    })
  );
  crownCap.position.y = 0.125;
  crownCap.castShadow = true;
  crownCap.userData = { kind: 'piece', square: piece.square, owner: piece.owner };
  group.add(crownCap);
  clickTargets.push(crownCap);
}

function renderBoard(data) {
  clearDynamic();
  const crownMap = new Map(data.game.crown_squares.map((entry) => [entry.square, entry.value]));
  const parity = data.game.variant.playable_parity;

  for (let rank = 1; rank <= 8; rank += 1) {
    for (let file = 0; file < 8; file += 1) {
      const square = `${String.fromCharCode(97 + file)}${rank}`;
      const playable = ((file + 1 + rank) % 2) === parity;
      const crown = crownMap.get(square);
      const darkSquare = ((file + rank) % 2 === 0);
      const baseColor = darkSquare ? 0x252c37 : 0xd5d0c5;
      const material = new THREE.MeshStandardMaterial({
        color: crown !== undefined ? 0x596b85 : baseColor,
        emissive: crown !== undefined && playable ? 0x111c2c : 0x000000,
        emissiveIntensity: crown !== undefined && playable ? 0.42 : 0,
        roughness: crown !== undefined ? 0.56 : 0.72,
        metalness: crown !== undefined ? 0.2 : 0.04,
        opacity: playable ? 1 : 0.39,
        transparent: !playable,
      });
      const tileHeight = crown !== undefined ? 0.145 : 0.1;
      const tile = new THREE.Mesh(new THREE.BoxGeometry(0.965, tileHeight, 0.965), material);
      const { x, z } = squareToWorld(square);
      tile.position.set(x, 0, z);
      tile.receiveShadow = true;
      tile.castShadow = crown !== undefined;
      tile.userData = { kind: 'square', square, playable };
      boardGroup.add(tile);
      dynamicObjects.push(tile);
      clickTargets.push(tile);
      tileObjects.set(square, tile);

      const mark = new THREE.Mesh(
        new THREE.PlaneGeometry(0.89, 0.89),
        new THREE.MeshBasicMaterial({
          map: squareMarkTexture(square, crown, darkSquare, playable),
          transparent: true,
          depthWrite: false,
          opacity: playable ? 1 : 0.55,
        })
      );
      mark.rotation.x = -Math.PI / 2;
      mark.position.set(x, tileHeight / 2 + 0.006, z);
      boardGroup.add(mark);
      dynamicObjects.push(mark);
    }
  }

  for (const piece of data.game.pieces) {
    const { x, z } = squareToWorld(piece.square);
    const group = new THREE.Group();
    const bodyMaterial = new THREE.MeshStandardMaterial({
      color: piece.owner === 'W' ? 0xf0ece1 : 0x171b22,
      emissive: piece.king ? 0x2c210c : 0x000000,
      emissiveIntensity: piece.king ? 0.42 : 0,
      roughness: piece.king ? 0.34 : 0.48,
      metalness: piece.king ? 0.34 : 0.08,
    });
    const body = new THREE.Mesh(
      new THREE.CylinderGeometry(0.37, 0.41, piece.king ? 0.30 : 0.22, 48),
      bodyMaterial
    );
    body.castShadow = true;
    body.receiveShadow = true;
    body.userData = { kind: 'piece', square: piece.square, owner: piece.owner };
    group.add(body);
    clickTargets.push(body);

    if (piece.king) addKingTreatment(group, piece);

    const top = new THREE.Mesh(
      new THREE.CircleGeometry(piece.king ? 0.245 : 0.28, 48),
      new THREE.MeshBasicMaterial({ map: pieceLabelTexture(piece), transparent: true })
    );
    top.rotation.x = -Math.PI / 2;
    top.position.y = piece.king ? 0.205 : 0.115;
    top.userData = { kind: 'piece', square: piece.square, owner: piece.owner };
    group.add(top);
    clickTargets.push(top);

    group.position.set(x, piece.king ? 0.235 : 0.17, z);
    boardGroup.add(group);
    dynamicObjects.push(group);
    pieceGroups.set(piece.square, group);
  }

  renderSelection();
}

function moveDetailsFrom(square) {
  return (state?.game.legal_move_details || []).filter((move) => move.origin === square);
}

function canHumanInteract() {
  if (!state || state.game.game_over || computerBusy || animationBusy) return false;
  return !(ui.opponent.value === 'computer' && state.game.turn_participant === 'B');
}

function renderSelection() {
  clearHighlights();
  if (!selectedSquare || !state) return;

  const origin = squareToWorld(selectedSquare);
  const ring = new THREE.Mesh(
    new THREE.RingGeometry(0.37, 0.47, 40),
    new THREE.MeshBasicMaterial({ color: 0x70b7ff, transparent: true, opacity: 0.95, side: THREE.DoubleSide })
  );
  ring.rotation.x = -Math.PI / 2;
  ring.position.set(origin.x, 0.19, origin.z);
  boardGroup.add(ring);
  highlightObjects.push(ring);

  const byDestination = new Map();
  for (const move of moveDetailsFrom(selectedSquare)) {
    if (!byDestination.has(move.destination)) byDestination.set(move.destination, []);
    byDestination.get(move.destination).push(move);
  }

  for (const [destination, moves] of byDestination.entries()) {
    const { x, z } = squareToWorld(destination);
    const capture = moves.some((move) => move.is_capture);
    const marker = new THREE.Mesh(
      new THREE.CircleGeometry(capture ? 0.24 : 0.19, 36),
      new THREE.MeshBasicMaterial({
        color: capture ? 0xffc857 : 0x5be38d,
        transparent: true,
        opacity: 0.9,
        side: THREE.DoubleSide,
      })
    );
    marker.rotation.x = -Math.PI / 2;
    marker.position.set(x, 0.17, z);
    boardGroup.add(marker);
    highlightObjects.push(marker);
  }
}

function selectPiece(square) {
  if (!canHumanInteract()) return;
  const piece = state.game.pieces.find((item) => item.square === square);
  if (!piece || piece.owner !== state.game.turn) {
    selectedSquare = null;
    renderSelection();
    return;
  }
  const moves = moveDetailsFrom(square);
  if (!moves.length) {
    statusOverride = 'That piece has no legal move this turn.';
    selectedSquare = null;
  } else {
    selectedSquare = square;
    statusOverride = `${square} selected · choose a highlighted destination.`;
  }
  renderSelection();
  renderUI(state);
}

function chooseDestination(square) {
  if (!selectedSquare || !canHumanInteract()) return;
  const candidates = moveDetailsFrom(selectedSquare).filter((move) => move.destination === square);
  if (!candidates.length) {
    selectedSquare = null;
    statusOverride = null;
    renderSelection();
    renderUI(state);
    return;
  }
  if (candidates.length === 1) {
    submitMove(candidates[0].notation);
    return;
  }

  ui.routeOptions.replaceChildren();
  for (const move of candidates) {
    const button = document.createElement('button');
    button.textContent = `${move.notation} · ${move.captured.length} capture${move.captured.length === 1 ? '' : 's'}`;
    button.addEventListener('click', async () => {
      ui.routeDialog.close();
      await submitMove(move.notation);
    });
    ui.routeOptions.appendChild(button);
  }
  ui.routeDialog.showModal();
}

function flashElement(element) {
  if (!element) return;
  element.classList.remove('value-pulse');
  void element.offsetWidth;
  element.classList.add('value-pulse');
  setTimeout(() => element.classList.remove('value-pulse'), 700);
}

function renderUI(data) {
  ui.game.textContent = `SET ${data.set.set_index} · GAME ${data.set.game_number}`;
  ui.turn.textContent = data.game.game_over
    ? `Game ${data.set.game_number} complete`
    : computerBusy
      ? 'Computer thinking…'
      : animationBusy
        ? 'Move in progress…'
        : `Player ${data.game.turn_participant} to move`;
  ui.variant.textContent = data.game.variant.name;
  ui.scoreA.textContent = data.set.aggregate.A;
  ui.scoreB.textContent = data.set.aggregate.B;
  ui.bankW.textContent = `${data.game.capture_banks.W} / 15`;
  ui.bankB.textContent = `${data.game.capture_banks.B} / 15`;
  ui.meldW.textContent = data.game.melds.W.length;
  ui.meldB.textContent = data.game.melds.B.length;

  ui.moves.replaceChildren();
  for (const move of data.game.legal_moves) {
    const button = document.createElement('button');
    button.textContent = move;
    button.disabled = !canHumanInteract();
    button.addEventListener('click', () => submitMove(move));
    ui.moves.appendChild(button);
  }

  ui.advance.hidden = !data.game.game_over || data.set.set_over;
  ui.advance.disabled = computerBusy || animationBusy;
  ui.reset.disabled = computerBusy || animationBusy;
  ui.opponent.disabled = computerBusy || animationBusy;
  ui.flip.disabled = animationBusy;

  if (statusOverride) {
    ui.status.textContent = statusOverride;
  } else if (data.set.set_over) {
    ui.status.textContent = `Set complete · ${data.set.winner === 'DRAW' ? 'Draw' : `Player ${data.set.winner} wins`} · A ${data.set.aggregate.A} — B ${data.set.aggregate.B}`;
  } else if (data.game.game_over) {
    ui.status.textContent = `Game score · White ${data.game.scores.W.total} — Black ${data.game.scores.B.total}`;
  } else if (data.game.triggering_player) {
    ui.status.textContent = `${data.game.triggering_player} crossed the capture quota. This is the final response turn.`;
  } else if (ui.opponent.value === 'computer' && data.game.turn_participant === 'B') {
    ui.status.textContent = computerBusy ? 'Computer is evaluating the position.' : 'Computer turn.';
  } else {
    ui.status.textContent = 'Click a piece, then a highlighted destination.';
  }
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  const payload = await response.json();
  if (!response.ok) {
    const error = new Error(payload.message || payload.error || 'Request failed');
    error.payload = payload;
    throw error;
  }
  return payload;
}

function setObjectOpacity(group, opacity) {
  group.traverse((object) => {
    if (!object.material) return;
    const materials = Array.isArray(object.material) ? object.material : [object.material];
    for (const material of materials) {
      material.transparent = true;
      material.opacity = opacity;
    }
  });
}

async function animateMove(previousState, moveNotation) {
  const detail = previousState?.game.legal_move_details?.find((move) => move.notation === moveNotation);
  if (!detail) return;
  const movingGroup = pieceGroups.get(detail.origin);
  if (!movingGroup) return;

  clearHighlights();
  clearCrownlinePreview();
  const baseY = movingGroup.position.y;
  for (let i = 1; i < detail.path.length; i += 1) {
    const from = { x: movingGroup.position.x, z: movingGroup.position.z };
    const to = squareToWorld(detail.path[i]);
    const capturedSquare = detail.captured[i - 1];
    const capturedGroup = capturedSquare ? pieceGroups.get(capturedSquare) : null;
    const capturedBaseY = capturedGroup?.position.y ?? 0;

    await tween(detail.is_capture ? 260 : 230, (t, raw) => {
      movingGroup.position.x = THREE.MathUtils.lerp(from.x, to.x, t);
      movingGroup.position.z = THREE.MathUtils.lerp(from.z, to.z, t);
      movingGroup.position.y = baseY + Math.sin(Math.PI * raw) * (detail.is_capture ? 0.42 : 0.20);

      if (capturedGroup && raw > 0.36) {
        const vanish = Math.min(1, (raw - 0.36) / 0.64);
        capturedGroup.scale.setScalar(1 - vanish * 0.54);
        capturedGroup.position.y = capturedBaseY + vanish * 0.34;
        setObjectOpacity(capturedGroup, 1 - vanish);
      }
    });

    movingGroup.position.set(to.x, baseY, to.z);
    if (capturedGroup) capturedGroup.visible = false;
  }
}

async function showEvent(text, tone = 'neutral', duration = 620) {
  if (!text) return;
  const serial = ++eventSerial;
  ui.eventBanner.textContent = text;
  ui.eventBanner.className = `event-banner ${tone}`;
  void ui.eventBanner.offsetWidth;
  ui.eventBanner.classList.add('show');
  await sleep(duration);
  if (serial !== eventSerial) return;
  ui.eventBanner.classList.remove('show');
  await sleep(150);
}

function newMelds(previousState, nextState, color) {
  const before = new Set((previousState?.game.melds?.[color] || []).map((meld) => meld.line.join('|')));
  return (nextState.game.melds?.[color] || []).filter((meld) => !before.has(meld.line.join('|')));
}

async function flashMeld(line) {
  if (!line?.length) return;
  clearCrownlinePreview();
  const positions = line.map((square) => {
    const p = squareToWorld(square);
    return new THREE.Vector3(p.x, 0.34, p.z);
  });
  const geometry = new THREE.BufferGeometry().setFromPoints(positions);
  const material = new THREE.LineBasicMaterial({ color: 0xf0c86a, transparent: true, opacity: 0 });
  const beam = new THREE.Line(geometry, material);
  boardGroup.add(beam);
  effectObjects.push(beam);

  const rings = line.map((square) => {
    const p = squareToWorld(square);
    const ring = new THREE.Mesh(
      new THREE.RingGeometry(0.32, 0.48, 48),
      new THREE.MeshBasicMaterial({
        color: 0xf0c86a,
        transparent: true,
        opacity: 0,
        blending: THREE.AdditiveBlending,
        side: THREE.DoubleSide,
        depthWrite: false,
      })
    );
    ring.rotation.x = -Math.PI / 2;
    ring.position.set(p.x, 0.26, p.z);
    boardGroup.add(ring);
    effectObjects.push(ring);
    return ring;
  });

  const tileBases = line.map((square) => {
    const tile = tileObjects.get(square);
    return tile ? { tile, intensity: tile.material.emissiveIntensity || 0 } : null;
  });

  await tween(1050, (t, raw) => {
    const pulse = Math.sin(Math.PI * raw);
    material.opacity = 0.18 + pulse * 0.82;
    for (const ring of rings) {
      ring.material.opacity = pulse * 0.92;
      const scale = 0.82 + pulse * 0.36;
      ring.scale.setScalar(scale);
    }
    for (const entry of tileBases) {
      if (entry) entry.tile.material.emissiveIntensity = entry.intensity + pulse * 1.45;
    }
  });

  for (const entry of tileBases) {
    if (entry) entry.tile.material.emissiveIntensity = entry.intensity;
  }
  clearEffects();
}

async function pulsePromotion(square) {
  const group = pieceGroups.get(square);
  if (!group) return;
  const original = group.scale.x;
  await tween(520, (_t, raw) => {
    const pulse = Math.sin(Math.PI * raw);
    const scale = original + pulse * 0.18;
    group.scale.setScalar(scale);
  });
  group.scale.setScalar(original);
}

async function announceMoveEffects(previousState, nextState, moveNotation) {
  const detail = previousState.game.legal_move_details.find((move) => move.notation === moveNotation);
  const mover = previousState.game.turn;
  const captureDelta = nextState.game.capture_banks[mover] - previousState.game.capture_banks[mover];
  const melds = newMelds(previousState, nextState, mover);
  const originPiece = previousState.game.pieces.find((piece) => piece.square === detail?.origin);
  const destinationPiece = nextState.game.pieces.find((piece) => piece.square === detail?.destination);
  const promoted = Boolean(originPiece && destinationPiece && !originPiece.king && destinationPiece.king);

  const messages = [];
  if (captureDelta > 0) messages.push(`CAPTURE +${captureDelta}`);
  if (melds.length) messages.push(`CROWNLINE +${melds.length * 15}`);
  if (promoted) messages.push('KING CROWNED');

  if (captureDelta > 0) flashElement(mover === 'W' ? ui.bankW.parentElement : ui.bankB.parentElement);
  if (melds.length) flashElement(mover === 'W' ? ui.meldW.parentElement : ui.meldB.parentElement);

  const effects = [];
  if (melds.length) effects.push(flashMeld(melds[0].line));
  if (promoted && detail?.destination) effects.push(pulsePromotion(detail.destination));
  if (messages.length) effects.push(showEvent(messages.join(' · '), melds.length || promoted ? 'gold' : 'capture'));
  if (effects.length) await Promise.all(effects);
}

async function applyAnimatedState(previousState, nextState, moveNotation) {
  await animateMove(previousState, moveNotation);
  state = nextState;
  renderBoard(state);
  renderUI(state);
  await announceMoveEffects(previousState, nextState, moveNotation);
}

async function refresh() {
  state = await api('/api/state');
  selectedSquare = null;
  statusOverride = null;
  renderBoard(state);
  renderUI(state);
  await maybeComputerMove();
}

async function submitMove(move, meldLine = null) {
  if (computerBusy || animationBusy) return;
  const previousState = state;
  try {
    animationBusy = true;
    selectedSquare = null;
    statusOverride = null;
    renderSelection();
    renderUI(state);

    const nextState = await api('/api/move', {
      method: 'POST',
      body: JSON.stringify({ move, meld_line: meldLine }),
    });
    await applyAnimatedState(previousState, nextState, move);
  } catch (error) {
    if (error.payload?.error === 'meld_choice_required') {
      pendingMove = move;
      ui.meldOptions.replaceChildren();
      for (const option of error.payload.options) {
        const button = document.createElement('button');
        button.textContent = `${option.line.join(' · ')}  |  pieces ${option.piece_ids.join(', ')}`;
        button.addEventListener('click', async () => {
          ui.meldDialog.close();
          animationBusy = false;
          await submitMove(pendingMove, option.line);
          pendingMove = null;
        });
        ui.meldOptions.appendChild(button);
      }
      ui.meldDialog.showModal();
      return;
    }
    statusOverride = error.message;
  } finally {
    if (!ui.meldDialog.open) animationBusy = false;
    renderUI(state);
  }

  await maybeComputerMove();
}

async function maybeComputerMove() {
  if (
    ui.opponent.value !== 'computer' ||
    !state ||
    state.set.set_over ||
    state.game.game_over ||
    state.game.turn_participant !== 'B' ||
    computerBusy ||
    animationBusy
  ) return;

  computerBusy = true;
  selectedSquare = null;
  statusOverride = null;
  renderSelection();
  renderUI(state);
  await sleep(420);

  const previousState = state;
  try {
    const nextState = await api('/api/computer-move', {
      method: 'POST',
      body: JSON.stringify({ participant: 'B', depth: 2 }),
    });
    const played = nextState.computer_action?.move;
    if (played) {
      animationBusy = true;
      await applyAnimatedState(previousState, nextState, played);
      statusOverride = `Computer played ${played}.`;
    } else {
      state = nextState;
      renderBoard(state);
    }
  } catch (error) {
    statusOverride = error.message;
  } finally {
    animationBusy = false;
    computerBusy = false;
    renderUI(state);
  }
}

async function playGameTransition(previousState, nextState) {
  animationBusy = true;
  renderUI(previousState);

  if (nextState.set.set_over) {
    ui.transitionTitle.textContent = nextState.set.winner === 'DRAW' ? 'SET DRAWN' : `PLAYER ${nextState.set.winner} WINS`;
    ui.transitionSub.textContent = `A ${nextState.set.aggregate.A} — B ${nextState.set.aggregate.B}`;
  } else {
    ui.transitionTitle.textContent = `GAME ${nextState.set.game_number}`;
    ui.transitionSub.textContent = nextState.set.game_number === 2
      ? 'Light squares · complementary Lo Shu'
      : nextState.game.variant.name;
  }

  ui.transition.classList.add('show');
  await tween(360, (t) => {
    const scale = THREE.MathUtils.lerp(1, 0.94, t);
    boardGroup.scale.setScalar(scale);
  });

  state = nextState;
  renderBoard(state);
  renderUI(state);
  boardGroup.scale.setScalar(0.94);
  await sleep(260);

  await tween(480, (t) => {
    const scale = THREE.MathUtils.lerp(0.94, 1, t);
    boardGroup.scale.setScalar(scale);
  });
  await sleep(220);
  ui.transition.classList.remove('show');

  if (previousState.set.aggregate.A !== nextState.set.aggregate.A) flashElement(ui.scoreCardA);
  if (previousState.set.aggregate.B !== nextState.set.aggregate.B) flashElement(ui.scoreCardB);
  animationBusy = false;
  renderUI(state);
}

ui.advance.addEventListener('click', async () => {
  if (animationBusy || computerBusy) return;
  try {
    const previousState = state;
    const nextState = await api('/api/advance', { method: 'POST', body: '{}' });
    selectedSquare = null;
    statusOverride = null;
    await playGameTransition(previousState, nextState);
    await maybeComputerMove();
  } catch (error) {
    animationBusy = false;
    statusOverride = error.message;
    renderUI(state);
  }
});

ui.reset.addEventListener('click', async () => {
  if (animationBusy || computerBusy) return;
  const nextState = await api('/api/reset', { method: 'POST', body: JSON.stringify({ first_game_white: 'A' }) });
  state = nextState;
  selectedSquare = null;
  statusOverride = null;
  renderBoard(state);
  renderUI(state);
  await showEvent('NEW SET', 'neutral', 420);
  await maybeComputerMove();
});

ui.opponent.addEventListener('change', async () => {
  localStorage.setItem('crownline-opponent', ui.opponent.value);
  statusOverride = null;
  renderUI(state);
  await maybeComputerMove();
});

ui.flip.addEventListener('click', () => {
  if (animationBusy) return;
  targetBoardRotation += Math.PI;
  localStorage.setItem('crownline-board-rotation', String(targetBoardRotation));
});

ui.meldCancel.addEventListener('click', () => {
  pendingMove = null;
  animationBusy = false;
  ui.meldDialog.close();
  renderUI(state);
});

ui.routeCancel.addEventListener('click', () => ui.routeDialog.close());

function updatePointer(event) {
  const rect = canvas.getBoundingClientRect();
  pointer.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
  pointer.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;
}

function handleBoardClick(event) {
  if (!canHumanInteract()) return;
  updatePointer(event);
  raycaster.setFromCamera(pointer, camera);
  const hit = raycaster.intersectObjects(clickTargets, false)[0];
  if (!hit) {
    selectedSquare = null;
    statusOverride = null;
    renderSelection();
    renderUI(state);
    return;
  }

  const { kind, square } = hit.object.userData;
  if (kind === 'piece') {
    if (selectedSquare === square) {
      selectedSquare = null;
      statusOverride = null;
      renderSelection();
      renderUI(state);
    } else {
      selectPiece(square);
    }
    return;
  }
  if (kind === 'square') chooseDestination(square);
}

canvas.addEventListener('pointerdown', (event) => {
  if (animationBusy) return;
  pointerDown = true;
  draggingBoard = false;
  dragStartX = event.clientX;
  dragStartY = event.clientY;
  dragLastX = event.clientX;
  pressEvent = event;
  canvas.setPointerCapture?.(event.pointerId);
});

canvas.addEventListener('pointermove', (event) => {
  if (!pointerDown) return;
  const total = Math.hypot(event.clientX - dragStartX, event.clientY - dragStartY);
  if (total > 5) draggingBoard = true;
  if (!draggingBoard) return;
  const dx = event.clientX - dragLastX;
  dragLastX = event.clientX;
  targetBoardRotation += dx * 0.0085;
  selectedSquare = null;
  statusOverride = null;
  renderSelection();
});

canvas.addEventListener('pointerup', (event) => {
  if (!pointerDown) return;
  const wasDragging = draggingBoard;
  pointerDown = false;
  draggingBoard = false;
  canvas.releasePointerCapture?.(event.pointerId);
  if (wasDragging) {
    localStorage.setItem('crownline-board-rotation', String(targetBoardRotation));
    renderUI(state);
    pressEvent = null;
    return;
  }
  handleBoardClick(pressEvent || event);
  pressEvent = null;
});

canvas.addEventListener('pointercancel', () => {
  pointerDown = false;
  draggingBoard = false;
  pressEvent = null;
});

function resize() {
  const width = canvas.clientWidth;
  const height = canvas.clientHeight;
  renderer.setSize(width, height, false);
  camera.aspect = width / height;
  camera.updateProjectionMatrix();
}

function animate(time = 0) {
  resize();
  const delta = targetBoardRotation - boardRotation;
  boardRotation += delta * 0.14;
  boardGroup.rotation.y = boardRotation;

  const pulse = 0.18 + (Math.sin(time * 0.004) + 1) * 0.07;
  boardGroup.traverse((object) => {
    if (object.userData?.pulse && object.material) object.material.opacity = pulse;
  });

  renderer.render(scene, camera);
  requestAnimationFrame(animate);
}

await refresh();
animate();
