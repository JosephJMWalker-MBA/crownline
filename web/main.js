import * as THREE from 'three';

const canvas = document.querySelector('#board');
const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
renderer.shadowMap.enabled = true;

const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(38, 1, 0.1, 100);
camera.position.set(7.7, 9.8, 10.8);
camera.lookAt(0, 0, 0);

scene.add(new THREE.HemisphereLight(0xdde7ff, 0x20232a, 2.25));
const key = new THREE.DirectionalLight(0xffffff, 4.0);
key.position.set(4, 10, 6);
key.castShadow = true;
scene.add(key);

const boardGroup = new THREE.Group();
scene.add(boardGroup);

const boardBase = new THREE.Mesh(
  new THREE.BoxGeometry(8.7, 0.34, 8.7),
  new THREE.MeshStandardMaterial({ color: 0x151922, roughness: 0.72, metalness: 0.1 })
);
boardBase.position.y = -0.26;
boardBase.receiveShadow = true;
boardGroup.add(boardBase);

const ui = {
  game: document.querySelector('#game-label'),
  turn: document.querySelector('#turn-label'),
  variant: document.querySelector('#variant-label'),
  scoreA: document.querySelector('#score-a'),
  scoreB: document.querySelector('#score-b'),
  bankW: document.querySelector('#bank-w'),
  bankB: document.querySelector('#bank-b'),
  meldW: document.querySelector('#meld-w'),
  meldB: document.querySelector('#meld-b'),
  moves: document.querySelector('#moves'),
  status: document.querySelector('#status'),
  advance: document.querySelector('#advance'),
  reset: document.querySelector('#reset'),
  opponent: document.querySelector('#opponent-mode'),
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
let statusOverride = null;

const dynamicObjects = [];
const clickTargets = [];
const highlightObjects = [];
const raycaster = new THREE.Raycaster();
const pointer = new THREE.Vector2();

ui.opponent.value = localStorage.getItem('crownline-opponent') || 'human';

function squareToWorld(square) {
  const file = square.charCodeAt(0) - 97;
  const rank = Number(square[1]) - 1;
  return { x: file - 3.5, z: 3.5 - rank };
}

function clearObjects(list) {
  while (list.length) {
    const object = list.pop();
    boardGroup.remove(object);
    object.traverse?.((child) => {
      child.geometry?.dispose?.();
      if (Array.isArray(child.material)) child.material.forEach((m) => m.dispose?.());
      else child.material?.dispose?.();
      child.material?.map?.dispose?.();
    });
  }
}

function clearDynamic() {
  clearHighlights();
  clearObjects(dynamicObjects);
  clickTargets.length = 0;
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
    ctx.font = '800 38px system-ui';
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
  ctx.fillStyle = lightText ? 'rgba(244,247,251,.88)' : 'rgba(22,26,33,.72)';
  ctx.font = '700 30px system-ui';
  ctx.textAlign = 'left';
  ctx.textBaseline = 'bottom';
  ctx.fillText(square, 18, 238);

  if (crown !== undefined) {
    ctx.fillStyle = playable ? '#f6f8fb' : 'rgba(246,248,251,.48)';
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
      const baseColor = darkSquare ? 0x262b35 : 0xd6d1c6;
      const material = new THREE.MeshStandardMaterial({
        color: crown !== undefined ? 0x58667a : baseColor,
        roughness: 0.78,
        metalness: crown !== undefined ? 0.18 : 0.02,
        opacity: playable ? 1 : 0.36,
        transparent: !playable,
      });
      const tileHeight = crown !== undefined ? 0.14 : 0.1;
      const tile = new THREE.Mesh(new THREE.BoxGeometry(0.98, tileHeight, 0.98), material);
      const { x, z } = squareToWorld(square);
      tile.position.set(x, 0, z);
      tile.receiveShadow = true;
      tile.userData = { kind: 'square', square, playable };
      boardGroup.add(tile);
      dynamicObjects.push(tile);
      clickTargets.push(tile);

      const mark = new THREE.Mesh(
        new THREE.PlaneGeometry(0.91, 0.91),
        new THREE.MeshBasicMaterial({
          map: squareMarkTexture(square, crown, darkSquare, playable),
          transparent: true,
          depthWrite: false,
          opacity: playable ? 1 : 0.58,
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
    const body = new THREE.Mesh(
      new THREE.CylinderGeometry(0.37, 0.41, piece.king ? 0.28 : 0.22, 48),
      new THREE.MeshStandardMaterial({
        color: piece.owner === 'W' ? 0xf0ece1 : 0x171b22,
        roughness: 0.48,
        metalness: piece.king ? 0.28 : 0.08,
      })
    );
    body.castShadow = true;
    body.receiveShadow = true;
    body.userData = { kind: 'piece', square: piece.square, owner: piece.owner };
    group.add(body);
    clickTargets.push(body);

    const top = new THREE.Mesh(
      new THREE.CircleGeometry(0.28, 48),
      new THREE.MeshBasicMaterial({ map: pieceLabelTexture(piece), transparent: true })
    );
    top.rotation.x = -Math.PI / 2;
    top.position.y = piece.king ? 0.145 : 0.115;
    top.userData = { kind: 'piece', square: piece.square, owner: piece.owner };
    group.add(top);
    clickTargets.push(top);

    group.position.set(x, piece.king ? 0.22 : 0.17, z);
    boardGroup.add(group);
    dynamicObjects.push(group);
  }

  renderSelection();
}

function moveDetailsFrom(square) {
  return (state?.game.legal_move_details || []).filter((move) => move.origin === square);
}

function canHumanInteract() {
  if (!state || state.game.game_over || computerBusy) return false;
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
        opacity: 0.88,
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

function renderUI(data) {
  ui.game.textContent = `SET ${data.set.set_index} · GAME ${data.set.game_number}`;
  ui.turn.textContent = data.game.game_over
    ? `Game ${data.set.game_number} complete`
    : computerBusy
      ? 'Computer thinking…'
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
  ui.advance.disabled = computerBusy;
  ui.reset.disabled = computerBusy;
  ui.opponent.disabled = computerBusy;

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

async function refresh() {
  state = await api('/api/state');
  selectedSquare = null;
  statusOverride = null;
  renderBoard(state);
  renderUI(state);
  await maybeComputerMove();
}

async function submitMove(move, meldLine = null) {
  if (computerBusy) return;
  try {
    selectedSquare = null;
    statusOverride = null;
    state = await api('/api/move', {
      method: 'POST',
      body: JSON.stringify({ move, meld_line: meldLine }),
    });
    renderBoard(state);
    renderUI(state);
    await maybeComputerMove();
  } catch (error) {
    if (error.payload?.error === 'meld_choice_required') {
      pendingMove = move;
      ui.meldOptions.replaceChildren();
      for (const option of error.payload.options) {
        const button = document.createElement('button');
        button.textContent = `${option.line.join(' · ')}  |  pieces ${option.piece_ids.join(', ')}`;
        button.addEventListener('click', async () => {
          ui.meldDialog.close();
          await submitMove(pendingMove, option.line);
          pendingMove = null;
        });
        ui.meldOptions.appendChild(button);
      }
      ui.meldDialog.showModal();
      return;
    }
    statusOverride = error.message;
    renderUI(state);
  }
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function maybeComputerMove() {
  if (
    ui.opponent.value !== 'computer' ||
    !state ||
    state.set.set_over ||
    state.game.game_over ||
    state.game.turn_participant !== 'B' ||
    computerBusy
  ) return;

  computerBusy = true;
  selectedSquare = null;
  statusOverride = null;
  renderSelection();
  renderUI(state);
  await sleep(420);

  try {
    state = await api('/api/computer-move', {
      method: 'POST',
      body: JSON.stringify({ participant: 'B', depth: 2 }),
    });
    const played = state.computer_action?.move;
    statusOverride = played ? `Computer played ${played}.` : null;
    renderBoard(state);
  } catch (error) {
    statusOverride = error.message;
  } finally {
    computerBusy = false;
    renderUI(state);
  }
}

ui.advance.addEventListener('click', async () => {
  try {
    state = await api('/api/advance', { method: 'POST', body: '{}' });
    selectedSquare = null;
    statusOverride = null;
    renderBoard(state);
    renderUI(state);
    await maybeComputerMove();
  } catch (error) {
    statusOverride = error.message;
    renderUI(state);
  }
});

ui.reset.addEventListener('click', async () => {
  state = await api('/api/reset', { method: 'POST', body: JSON.stringify({ first_game_white: 'A' }) });
  selectedSquare = null;
  statusOverride = null;
  renderBoard(state);
  renderUI(state);
  await maybeComputerMove();
});

ui.opponent.addEventListener('change', async () => {
  localStorage.setItem('crownline-opponent', ui.opponent.value);
  statusOverride = null;
  renderUI(state);
  await maybeComputerMove();
});

ui.meldCancel.addEventListener('click', () => {
  pendingMove = null;
  ui.meldDialog.close();
});

ui.routeCancel.addEventListener('click', () => {
  ui.routeDialog.close();
});

canvas.addEventListener('pointerdown', (event) => {
  if (!canHumanInteract()) return;
  const rect = canvas.getBoundingClientRect();
  pointer.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
  pointer.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;
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
  if (kind === 'square') {
    chooseDestination(square);
  }
});

function resize() {
  const width = canvas.clientWidth;
  const height = canvas.clientHeight;
  renderer.setSize(width, height, false);
  camera.aspect = width / height;
  camera.updateProjectionMatrix();
}

function animate() {
  resize();
  renderer.render(scene, camera);
  requestAnimationFrame(animate);
}

await refresh();
animate();
