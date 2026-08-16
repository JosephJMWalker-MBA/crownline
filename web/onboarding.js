const nativeFetch = window.fetch.bind(window);

const guide = document.querySelector('#guide-dialog');
const guideKicker = document.querySelector('#guide-kicker');
const guideTitle = document.querySelector('#guide-title');
const guideCopy = document.querySelector('#guide-copy');
const guideProgress = document.querySelector('#guide-progress');
const guideBack = document.querySelector('#guide-back');
const guideNext = document.querySelector('#guide-next');
const guideSkip = document.querySelector('#guide-skip');
const guideClose = document.querySelector('#guide-close');
const help = document.querySelector('#help-dialog');
const helpButton = document.querySelector('#help-button');
const helpClose = document.querySelector('#help-close');
const helpContent = document.querySelector('#help-content');
const replayTutorial = document.querySelector('#replay-tutorial');
const profileTutorial = document.querySelector('#profile-tutorial');
const trackerHelp = document.querySelector('#tracker-help');
const tracker = document.querySelector('#crownline-tracker');
const trackerW = document.querySelector('#tracker-w');
const trackerB = document.querySelector('#tracker-b');
const trackerWLabel = document.querySelector('#tracker-w-label');
const trackerBLabel = document.querySelector('#tracker-b-label');
const ruleFeedback = document.querySelector('#rule-feedback');
const ruleFeedbackTitle = document.querySelector('#rule-feedback-title');
const ruleFeedbackCopy = document.querySelector('#rule-feedback-copy');

const GLOBAL_SEEN = 'crownline-onboarding-v2';
const PROFILE_SEEN = (mode) => `crownline-profile-guide-v4:${mode}`;

let latestState = null;
let previousState = null;
let guideScreens = [];
let guideIndex = 0;
let guideSeenKey = null;
let guideComplete = null;
let feedbackTimer = null;
let activeHelpTab = 'basics';

const globalScreens = [
  {
    kicker: 'WELCOME TO CROWNLINE',
    title: 'One set. Two games.',
    copy: `<p>Crownline is a strategy game of <strong>movement, mathematics, and position</strong>.</p>
      <p>You play <strong>two games per set</strong>. Game 1 uses the dark squares. Game 2 uses the light squares.</p>
      <p>Your scores from both games are added together. <strong>Highest total wins the set.</strong></p>`,
  },
  {
    kicker: 'MOVEMENT',
    title: 'Move like checkers.',
    copy: `<ul>
      <li>Pieces move diagonally forward.</li>
      <li>If a capture is available, you normally <strong>must take it</strong>.</li>
      <li>Multiple captures continue in the same turn.</li>
      <li>Reach the opposite edge to become a <strong>King</strong>.</li>
      <li>Kings move forward or backward.</li>
    </ul>
    <p>Captured pieces score their printed value. A captured King is worth <strong>double</strong>.</p>`,
  },
  {
    kicker: 'SCORING',
    title: 'The number 15 runs through the game.',
    copy: `<span class="hero-number">15</span>
      <p>Reach <strong>15 capture points</strong> and your opponent receives one final response turn.</p>
      <p>Then the game is scored:</p>
      <p><strong>Capture Bank + Board Value + Crownline Bonuses</strong></p>`,
  },
  {
    kicker: 'THE CROWN GRID',
    title: 'The board hides another game.',
    copy: `<p>Nine special squares form a 3×3 Crown Grid based on the Lo Shu magic square:</p>
      <div class="magic-grid">8 1 6<br>3 5 7<br>4 9 2</div>
      <p>Every row, column, and diagonal totals <strong>15</strong>.</p>
      <p>Your active Rules profile determines exactly what a three-piece Crownline must do to score.</p>`,
  },
  {
    kicker: 'THE SET',
    title: 'One game is only half the match.',
    copy: `<p>After Game 1, the playable square color changes, players swap sides and first move, and Crown values become complementary.</p>
      <p><strong>Your Game 1 points remain.</strong> Game 2 is added to them.</p>
      <p>If the aggregate totals are equal after both games, the set is a <strong>draw</strong>.</p>`,
  },
];

const crownedCoreScreens = (kicker) => [
  {
    kicker,
    title: 'No crown, no Crownline.',
    copy: `<p>A scoring Crownline must contain <strong>at least one King</strong>.</p>
      <p>Three pieces may occupy a geometric line without scoring if none of them has been crowned.</p>`,
  },
  {
    kicker,
    title: 'Build the line.',
    copy: `<p>Complete an available Crownline with three eligible pieces.</p>
      <p><strong>Crownline: +15</strong></p>
      <p>If all three pieces are Kings: <strong>ROYAL CROWNLINE +30</strong>.</p>`,
  },
  {
    kicker,
    title: 'The pieces must recover.',
    copy: `<p>After scoring, all three participating pieces receive a <strong>3-turn Crown cooldown</strong>.</p>
      <p>The board marks them <strong>³ → ² → ¹ → ready</strong>.</p>
      <p>They still move, capture, defend, and promote normally. Only Crownline scoring is unavailable. Only <strong>your own turns</strong> reduce your cooldown.</p>`,
  },
  {
    kicker,
    title: 'A scored line retires for you.',
    copy: `<p>Each of the eight Crownline geometries may score <strong>once per player per game</strong>.</p>
      <p>Your opponent may still score the same geometry. After you claim it, your Crownline Map marks it retired.</p>
      <p>This prevents repeating one profitable position forever.</p>`,
  },
  {
    kicker,
    title: 'Create. Recover. Reposition.',
    copy: `<p>The same pieces may score again after cooldown—but they must newly complete a <strong>different Crownline you have not retired</strong>.</p>
      <p><strong>Promote → form Crownline → score → cooldown → find another line.</strong></p>
      <p>The Crownline Map in the sidebar shows what remains available. Hover any listed geometry to see it glow on the board.</p>`,
  },
];

const profileScreens = {
  official: [
    {
      kicker: 'OFFICIAL v1.0',
      title: 'The frozen base rules.',
      copy: `<p>Kings move in both directions but remain subject to <strong>mandatory capture</strong>.</p>
        <p>A Crownline uses three eligible piece identities. Once an identity contributes to a banked meld in Official v1.0, that identity cannot be used in another meld during that game.</p>
        <p>This profile is the normative ruleset recorded in <strong>RULES.md</strong>.</p>`,
    },
  ],
  sovereign: [
    {
      kicker: 'EXPERIMENTAL · SOVEREIGN KING',
      title: 'A King can release the turn.',
      copy: `<p>If one of your Kings has an available capture, you may <strong>decline the capture obligation for that turn</strong>.</p>
        <p>You may then make <strong>any otherwise legal non-capturing move with any of your pieces</strong>. You do not have to move the King.</p>
        <p>If only ordinary pieces can capture, mandatory capture still applies.</p>`,
    },
    {
      kicker: 'SOVEREIGN KING',
      title: 'Freedom has a price.',
      copy: `<p>If you choose a King capture, that King must still complete the legal multiple-jump sequence.</p>
        <p>Kings also remain worth <strong>double their printed value</strong> when captured.</p>
        <p>This profile isolates King agency for comparison.</p>`,
    },
  ],
  crowned: crownedCoreScreens('EXPERIMENTAL · CROWNED MELD'),
  candidate: [
    {
      kicker: 'EXPERIMENTAL · CROWNLINE v1.1 CANDIDATE',
      title: 'The crown grants agency.',
      copy: `<p>This candidate combines the two strongest playtest rules.</p>
        <p><strong>Kings are Sovereign:</strong> when one of your Kings has an available capture, you may decline capture for the turn and make any otherwise legal non-capturing move with any piece.</p>
        <p>If only ordinary pieces can capture, mandatory capture still applies. A King that captures must finish its legal multi-jump.</p>`,
    },
    ...crownedCoreScreens('CROWNLINE v1.1 CANDIDATE'),
    {
      kicker: 'CROWNLINE v1.1 CANDIDATE',
      title: 'Why the rules work together.',
      copy: `<p>Promotion now changes the strategic phase of the game.</p>
        <p>A King can release the turn from a forced capture, allowing you to choose between <strong>capture, defense, Crownline construction, and Crownline denial</strong>—but Kings remain worth double when captured.</p>
        <p>This is the leading candidate for the next Official Crownline ruleset.</p>`,
    },
  ],
};

function markSeen(key) {
  if (key) localStorage.setItem(key, '1');
}

function isSeen(key) {
  return localStorage.getItem(key) === '1';
}

function isCrownedMode(mode) {
  return mode === 'crowned' || mode === 'candidate';
}

function renderGuide() {
  const screen = guideScreens[guideIndex];
  if (!screen) return;
  guideKicker.textContent = screen.kicker;
  guideTitle.textContent = screen.title;
  guideCopy.innerHTML = screen.copy;
  guideProgress.replaceChildren();
  guideScreens.forEach((_item, index) => {
    const mark = document.createElement('span');
    if (index === guideIndex) mark.classList.add('active');
    guideProgress.appendChild(mark);
  });
  guideBack.disabled = guideIndex === 0;
  guideNext.textContent = guideIndex === guideScreens.length - 1 ? 'Finish' : 'Next';
}

function openGuide(screens, seenKey = null, onComplete = null) {
  guideScreens = screens;
  guideIndex = 0;
  guideSeenKey = seenKey;
  guideComplete = onComplete;
  renderGuide();
  if (!guide.open) guide.showModal();
}

function finishGuide(mark = true) {
  if (mark) markSeen(guideSeenKey);
  if (guide.open) guide.close();
  const callback = guideComplete;
  guideComplete = null;
  if (callback) setTimeout(callback, 100);
}

function openProfileGuide(mode, mark = true) {
  const screens = profileScreens[mode] || profileScreens.official;
  openGuide(screens, mark ? PROFILE_SEEN(mode) : null);
}

guideBack.addEventListener('click', () => {
  if (guideIndex > 0) guideIndex -= 1;
  renderGuide();
});
guideNext.addEventListener('click', () => {
  if (guideIndex < guideScreens.length - 1) {
    guideIndex += 1;
    renderGuide();
  } else {
    finishGuide(true);
  }
});
guideSkip.addEventListener('click', () => finishGuide(true));
guideClose.addEventListener('click', () => finishGuide(true));

function showFeedback(title, copy, duration = 4200) {
  if (!ruleFeedback) return;
  clearTimeout(feedbackTimer);
  ruleFeedbackTitle.textContent = title;
  ruleFeedbackCopy.textContent = copy;
  ruleFeedback.hidden = false;
  feedbackTimer = setTimeout(() => {
    ruleFeedback.hidden = true;
  }, duration);
}

function renderTracker(data) {
  const mode = data?.set?.rules?.mode;
  const crowned = isCrownedMode(mode);
  tracker.hidden = !crowned;
  if (!crowned) return;

  trackerWLabel.textContent = `PLAYER ${data.set.white_participant} · WHITE`;
  trackerBLabel.textContent = `PLAYER ${data.set.black_participant} · BLACK`;

  for (const [color, target] of [['W', trackerW], ['B', trackerB]]) {
    target.replaceChildren();
    for (const item of data.game.crownline_tracker?.[color] || []) {
      const row = document.createElement('div');
      row.className = `tracker-item${item.retired ? ' retired' : ''}`;
      row.title = item.line.join(' · ');
      row.tabIndex = 0;
      row.setAttribute('aria-label', `${item.name}: ${item.line.join(', ')}${item.retired ? ', retired' : ', available'}`);
      const mark = document.createElement('span');
      mark.className = 'mark';
      mark.textContent = item.retired ? '✓' : '○';
      const label = document.createElement('span');
      label.textContent = item.name;
      row.append(mark, label);
      target.appendChild(row);
    }
  }
}

function currentRulesHtml(mode) {
  if (mode === 'candidate') {
    return `<h3>Experimental · Crownline v1.1 Candidate</h3>
      <p><strong>Sovereign Kings:</strong> if a King has an available capture, you may decline capture for the turn and make any otherwise legal non-capturing move with any piece. If only ordinary pieces can capture, mandatory capture still applies. A King that captures must finish its legal multi-jump.</p>
      <p><strong>Crowned Meld:</strong> a Crownline needs at least one King. Normal +15; three Kings = Royal +30. Scoring pieces cool down for 3 of their player's turns. Each Crownline geometry may score once per player per game.</p>`;
  }
  if (mode === 'sovereign') {
    return `<h3>Experimental · Sovereign King</h3>
      <p>If a King has an available capture, you may decline capture for the turn and make any otherwise legal non-capturing move with any piece. If only ordinary pieces can capture, mandatory capture still applies. A King that captures must finish its legal multi-jump.</p>`;
  }
  if (mode === 'crowned') {
    return `<h3>Experimental · Crowned Meld</h3>
      <p>A Crownline needs at least one King. A normal Crownline scores <strong>+15</strong>; three Kings score a Royal <strong>+30</strong>.</p>
      <p>Scoring pieces cool down for 3 of their player's turns. Each Crownline geometry may score once per player per game. Recovered pieces may later score a different available line.</p>`;
  }
  return `<h3>Official v1.0</h3>
    <p>Kings remain subject to mandatory capture. Banked Crownlines use the original v1.0 permanent piece-identity eligibility rule.</p>`;
}

function renderHelp(tab = activeHelpTab) {
  activeHelpTab = tab;
  document.querySelectorAll('[data-help-tab]').forEach((button) => {
    button.classList.toggle('active', button.dataset.helpTab === tab);
  });

  if (tab === 'scoring') {
    helpContent.innerHTML = `<h3>Game score</h3><p><strong>Capture Bank + Board Value + Crownline Bonuses</strong></p>
      <h3>Capture bank</h3><p>Captured pieces score their printed value. Captured Kings are worth double.</p>
      <h3>Endgame</h3><p>15 capture points triggers one final response turn, then the game is scored.</p>
      <h3>Set score</h3><p>Game 1 + Game 2. Highest aggregate wins.</p>`;
  } else if (tab === 'crownlines') {
    const mode = latestState?.set?.rules?.mode || 'official';
    helpContent.innerHTML = `<h3>The Crown Grid</h3><p><code>8 1 6 / 3 5 7 / 4 9 2</code></p>
      <p>Every row, column, and diagonal totals 15.</p>
      ${currentRulesHtml(mode)}
      ${isCrownedMode(mode) ? '<p>The live Crownline Map shows which geometries each player has retired. Hover or keyboard-focus a listed line to preview its exact squares on the board.</p>' : ''}`;
  } else if (tab === 'current') {
    helpContent.innerHTML = currentRulesHtml(latestState?.set?.rules?.mode || 'official');
  } else {
    helpContent.innerHTML = `<h3>Movement</h3><p>Move diagonally. Captures are mandatory unless the active Rules profile explicitly says otherwise.</p>
      <h3>Promotion</h3><p>Reach the opposite edge to become a King. Kings move forward and backward.</p>
      <h3>The set</h3><p>Game 1 uses dark squares. Game 2 uses light squares with complementary Crown values, and players swap sides and first move.</p>`;
  }
}

helpButton.addEventListener('click', () => {
  renderHelp(activeHelpTab);
  help.showModal();
});
helpClose.addEventListener('click', () => help.close());
document.querySelectorAll('[data-help-tab]').forEach((button) => {
  button.addEventListener('click', () => renderHelp(button.dataset.helpTab));
});
replayTutorial.addEventListener('click', () => {
  help.close();
  openGuide(globalScreens, null);
});
profileTutorial.addEventListener('click', () => {
  help.close();
  openProfileGuide(latestState?.set?.rules?.mode || 'official', false);
});
trackerHelp.addEventListener('click', () => {
  activeHelpTab = 'crownlines';
  renderHelp('crownlines');
  help.showModal();
});

function pieceMap(data) {
  const map = new Map();
  for (const piece of data?.game?.pieces || []) map.set(`${piece.owner}:${piece.piece_id}`, piece);
  return map;
}

function maybeContextual(previous, next) {
  if (!previous || !next) return;
  const mode = next.set.rules?.mode || 'official';

  const beforePieces = pieceMap(previous);
  for (const piece of next.game.pieces || []) {
    const before = beforePieces.get(`${piece.owner}:${piece.piece_id}`);
    if (before && !before.king && piece.king && !isSeen('crownline-tip:promotion-v3')) {
      markSeen('crownline-tip:promotion-v3');
      const suffix = mode === 'candidate'
        ? ' In the v1.1 Candidate, if this King later has a capture, you may decline capture for the turn and move another legal piece instead; Kings also unlock Crownline scoring.'
        : mode === 'sovereign'
          ? ' In Sovereign, if this King later has a capture, you may decline capture for the turn and move another legal piece instead.'
          : mode === 'crowned'
            ? ' In Crowned Meld, Kings unlock Crownline scoring.'
            : ' In Official v1.0, Kings are still subject to mandatory capture.';
      showFeedback('KING CROWNED', `Kings move forward and backward.${suffix}`);
      return;
    }
  }

  if (isCrownedMode(mode)) {
    const ready = [];
    for (const piece of next.game.pieces || []) {
      const before = beforePieces.get(`${piece.owner}:${piece.piece_id}`);
      if (before?.cooldown > 0 && piece.cooldown === 0) ready.push(piece.piece_id);
    }
    if (ready.length) showFeedback('CROWN READY', `Piece${ready.length > 1 ? 's' : ''} ${ready.join(', ')} may score Crownlines again.`);
  }
}

function handleMoveFeedback(payload) {
  const feedback = payload?.move_feedback;
  if (!feedback || feedback.meld_scored || !feedback.meld_diagnostics?.length) return;
  if (payload.computer_action) return;
  const diagnostic = feedback.meld_diagnostics[0];
  const copy = diagnostic.reasons.map((reason) => reason.message).join(' ');
  showFeedback('NO CROWNLINE', copy, 5200);
}

function applyState(data) {
  if (!data?.set || !data?.game) return;
  previousState = latestState;
  latestState = data;
  renderTracker(data);
  if (help.open) renderHelp(activeHelpTab);
  maybeContextual(previousState, latestState);
}

// Install the bridge before main.js. The authoritative Python response carries
// explanations; this layer only displays them and updates educational UI.
window.fetch = async (...args) => {
  const response = await nativeFetch(...args);
  try {
    const request = args[0];
    const url = typeof request === 'string' ? request : request?.url || '';
    if (url.includes('/api/')) {
      const payload = await response.clone().json();
      if (response.ok) {
        queueMicrotask(() => {
          applyState(payload);
          handleMoveFeedback(payload);
        });
      }
    }
  } catch (_error) {
    // Educational feedback must never interfere with gameplay requests.
  }
  return response;
};

async function bootstrap() {
  try {
    const response = await nativeFetch('/api/state');
    if (!response.ok) return;
    const data = await response.json();
    applyState(data);
    const mode = data.set.rules?.mode || 'official';

    if (!isSeen(GLOBAL_SEEN)) {
      openGuide(globalScreens, GLOBAL_SEEN, () => {
        if (!isSeen(PROFILE_SEEN(mode))) openProfileGuide(mode, true);
      });
    } else if (!isSeen(PROFILE_SEEN(mode))) {
      openProfileGuide(mode, true);
    }
  } catch (_error) {
    // The game remains usable even if onboarding cannot initialize.
  }
}

await bootstrap();