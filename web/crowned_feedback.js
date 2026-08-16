const banner = document.querySelector('#event-banner');
const meldW = document.querySelector('#meld-w');
const meldB = document.querySelector('#meld-b');
const note = document.querySelector('#rules-note');

let lastCounts = { W: Number(meldW?.textContent || 0), B: Number(meldB?.textContent || 0) };
let serial = 0;

async function getState() {
  const response = await fetch('/api/state');
  if (!response.ok) return null;
  return response.json();
}

function announce(text) {
  if (!banner || !text) return;
  const current = ++serial;
  setTimeout(() => {
    if (current !== serial) return;
    banner.textContent = text;
    banner.className = 'event-banner gold show';
    setTimeout(() => {
      if (current === serial) banner.classList.remove('show');
    }, 900);
  }, 90);
}

async function sync(initial = false) {
  const data = await getState();
  if (!data) return;

  for (const color of ['W', 'B']) {
    const melds = data.game.melds?.[color] || [];
    const previousCount = lastCounts[color];

    if (!initial && melds.length > previousCount) {
      const latest = melds[melds.length - 1];
      if (latest.royal) announce('ROYAL CROWNLINE +30');
    }

    lastCounts[color] = melds.length;
  }

  const mode = data.set.rules?.mode;
  if ((mode === 'crowned' || mode === 'candidate') && note) {
    note.title = 'A superscript on a piece (³, ², ¹) is its remaining Crownline cooldown.';
  }
}

const observer = new MutationObserver(() => sync(false));
if (meldW) observer.observe(meldW, { childList: true, characterData: true, subtree: true });
if (meldB) observer.observe(meldB, { childList: true, characterData: true, subtree: true });

await sync(true);
