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
  meldDialog: document.querySelector('#meld-dialog'),
  meldOptions: document.querySelector('#meld-options'),
  meldCancel: document.querySelector('#meld-cancel'),
};

let state = null;
let pendingMove = null;
const dynamicObjects = [];

function squareToWorld(square) {
  const file = square.charCodeAt(0) - 97;
  const rank = Number(square[1]) - 1;
  return { x: file - 3.5, z: 3.5 - rank };
}

function clearDynamic() {
  while (dynamicObjects.length) {
    const object = dynamicObjects.pop();
    boardGroup.remove(object);
    object.traverse?.((child) => {
      child.geometry?.dispose?.();
      if (Array.isArray(child.material)) child.material.forEach((m) => m.dispose?.());
      else child.material?.dispose?.();
      child.material?.map?.dispose?.();
    });
  }
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
    ctx.font = '700 40px system-ui';
    ctx.fillText('K', 128, 48);
  }
  const texture = new THREE.CanvasTexture(canvas2d);
  texture.colorSpace = THREE.SRGBColorSpace;
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
      const baseColor = ((file + rank) % 2 === 0) ? 0x262b35 : 0xd6d1c6;
      const material = new THREE.MeshStandardMaterial({
        color: crown !== undefined ? 0x58667a : baseColor,
        roughness: 0.78,
        metalness: crown !== undefined ? 0.18 : 0.02,
        opacity: playable ? 1 : 0.36,
        transparent: !playable,
      });
      const tile = new THREE.Mesh(new THREE.BoxGeometry(0.98, crown !== undefined ? 0.14 : 0.1, 0.98), material);
      const { x, z } = squareToWorld(square);
      tile.position.set(x, 0, z);
      tile.receiveShadow = true;
      boardGroup.add(tile);
      dynamicObjects.push(tile);

      if (crown !== undefined) {
        const label = document.createElement('canvas');
        label.width = 128;
        label.height = 128;
        const ctx = label.getContext('2d');
        ctx.fillStyle = '#f4f7fb';
        ctx.font = '800 70px system-ui';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText(String(crown), 64, 68);
        const texture = new THREE.CanvasTexture(label);
        texture.colorSpace = THREE.SRGBColorSpace;
        const sprite = new THREE.Sprite(new THREE.SpriteMaterial({ map: texture, transparent: true, opacity: 0.72 }));
        sprite.scale.set(0.38, 0.38, 0.38);
        sprite.position.set(x, 0.09, z);
        sprite.rotation.x = -Math.PI / 2;
        boardGroup.add(sprite);
        dynamicObjects.push(sprite);
      }
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
    group.add(body);

    const top = new THREE.Mesh(
      new THREE.CircleGeometry(0.28, 48),
      new THREE.MeshBasicMaterial({ map: pieceLabelTexture(piece), transparent: true })
    );
    top.rotation.x = -Math.PI / 2;
    top.position.y = piece.king ? 0.145 : 0.115;
    group.add(top);
    group.position.set(x, piece.king ? 0.22 : 0.17, z);
    boardGroup.add(group);
    dynamicObjects.push(group);
  }
}

function renderUI(data) {
  ui.game.textContent = `SET ${data.set.set_index} · GAME ${data.set.game_number}`;
  ui.turn.textContent = data.game.game_over
    ? `Game ${data.set.game_number} complete`
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
    button.addEventListener('click', () => submitMove(move));
    ui.moves.appendChild(button);
  }

  ui.advance.hidden = !data.game.game_over || data.set.set_over;
  if (data.set.set_over) {
    ui.status.textContent = `Set complete · ${data.set.winner === 'DRAW' ? 'Draw' : `Player ${data.set.winner} wins`} · A ${data.set.aggregate.A} — B ${data.set.aggregate.B}`;
  } else if (data.game.game_over) {
    ui.status.textContent = `Game score · White ${data.game.scores.W.total} — Black ${data.game.scores.B.total}`;
  } else if (data.game.triggering_player) {
    ui.status.textContent = `${data.game.triggering_player} crossed the capture quota. This is the final response turn.`;
  } else {
    ui.status.textContent = `Game score now · White ${data.game.scores.W.total} — Black ${data.game.scores.B.total}`;
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
  renderBoard(state);
  renderUI(state);
}

async function submitMove(move, meldLine = null) {
  try {
    state = await api('/api/move', {
      method: 'POST',
      body: JSON.stringify({ move, meld_line: meldLine }),
    });
    renderBoard(state);
    renderUI(state);
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
    ui.status.textContent = error.message;
  }
}

ui.advance.addEventListener('click', async () => {
  try {
    state = await api('/api/advance', { method: 'POST', body: '{}' });
    renderBoard(state);
    renderUI(state);
  } catch (error) {
    ui.status.textContent = error.message;
  }
});

ui.reset.addEventListener('click', async () => {
  state = await api('/api/reset', { method: 'POST', body: JSON.stringify({ first_game_white: 'A' }) });
  renderBoard(state);
  renderUI(state);
});

ui.meldCancel.addEventListener('click', () => {
  pendingMove = null;
  ui.meldDialog.close();
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
