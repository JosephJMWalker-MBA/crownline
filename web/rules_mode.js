const select = document.querySelector('#rules-mode');
const note = document.querySelector('#rules-note');

function explain(mode) {
  const experimental = mode !== 'official';
  select.dataset.experimental = String(experimental);
  note.classList.toggle('experimental', experimental);

  if (mode === 'sovereign') {
    note.textContent = 'Experimental Sovereign · Kings may decline mandatory capture and make a legal King step.';
  } else if (mode === 'crowned') {
    note.textContent = 'Experimental Crowned Meld · Needs a King; pieces cool down for 3 turns; each line scores once per player; three Kings score Royal +30.';
  } else {
    note.textContent = 'Official v1.0 · Kings remain subject to mandatory capture.';
  }
}

async function request(path, options = {}) {
  const response = await fetch(path, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.message || payload.error || 'Request failed');
  return payload;
}

async function syncFromServer() {
  const data = await request('/api/state');
  const mode = data.set.rules?.mode || 'official';
  select.value = mode;
  select.dataset.current = mode;
  explain(mode);
  return data;
}

select.addEventListener('change', async () => {
  const desired = select.value;
  const previous = select.dataset.current || 'official';

  try {
    const current = await request('/api/state');
    const setHasStarted = current.game.ply > 0 || current.set.completed_games.length > 0;

    if (setHasStarted) {
      const confirmed = window.confirm(
        'Changing the rules profile starts a new Crownline Set. Continue?'
      );
      if (!confirmed) {
        select.value = previous;
        explain(previous);
        return;
      }
    }

    select.disabled = true;
    await request('/api/reset', {
      method: 'POST',
      body: JSON.stringify({
        first_game_white: current.set.first_game_white,
        rules_mode: desired,
      }),
    });
    window.location.reload();
  } catch (error) {
    select.value = previous;
    explain(previous);
    select.disabled = false;
    note.textContent = `Could not change rules: ${error.message}`;
    note.classList.add('experimental');
  }
});

try {
  await syncFromServer();
} catch (error) {
  select.disabled = true;
  note.textContent = `Rules profile unavailable: ${error.message}`;
  note.classList.add('experimental');
}
