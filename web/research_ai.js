(() => {
  const aiProfile = document.querySelector('#ai-profile');
  const opponent = document.querySelector('#opponent-mode');
  const rulesMode = document.querySelector('#rules-mode');
  const note = document.querySelector('#ai-profile-note');
  if (!aiProfile || !opponent || !rulesMode) return;

  const STORAGE_KEY = 'crownline-ai-profile';
  const validProfiles = new Set(['baseline', 'research']);
  const saved = localStorage.getItem(STORAGE_KEY);
  aiProfile.value = validProfiles.has(saved) ? saved : 'baseline';

  function refreshProfileAvailability() {
    const candidateRules = rulesMode.value === 'candidate';
    const researchOption = aiProfile.querySelector('option[value="research"]');
    if (researchOption) researchOption.disabled = !candidateRules;

    if (!candidateRules && aiProfile.value === 'research') {
      aiProfile.value = 'baseline';
      localStorage.setItem(STORAGE_KEY, 'baseline');
    }

    aiProfile.disabled = opponent.value !== 'computer';
    if (note) {
      if (aiProfile.value === 'research') {
        note.textContent = 'Research / Strong · 150 ms iterative search · structural TT · p200 repeat policy · promotion maturity w10.';
      } else if (!candidateRules) {
        note.textContent = 'Baseline A is available across legacy and experimental rules. Research / Strong is validated only for Crownline v1.1.';
      } else {
        note.textContent = 'Baseline A · depth 2 · original deterministic browser opponent.';
      }
    }
  }

  aiProfile.addEventListener('change', () => {
    localStorage.setItem(STORAGE_KEY, aiProfile.value);
    refreshProfileAvailability();
  });
  opponent.addEventListener('change', refreshProfileAvailability);
  rulesMode.addEventListener('change', () => setTimeout(refreshProfileAvailability, 0));

  // This script is intentionally loaded as a classic script before main.js's
  // deferred module executes. main.js restores the saved opponent mode from
  // localStorage, which does not emit a change event. Re-check once the page is
  // fully loaded so a previously saved Computer opponent cannot leave this
  // selector incorrectly disabled at Baseline A.
  window.addEventListener('load', refreshProfileAvailability, { once: true });
  refreshProfileAvailability();

  // main.js remains authoritative for when the computer moves. This small
  // transport shim adds only the selected AI profile to that existing request,
  // keeping presentation/UI changes separate from rules and search code.
  const nativeFetch = window.fetch.bind(window);
  window.fetch = (input, init = {}) => {
    const url = typeof input === 'string' ? input : input?.url;
    if (url) {
      const path = new URL(url, window.location.href).pathname;
      if (path === '/api/computer-move' && init?.body) {
        try {
          const payload = JSON.parse(init.body);
          payload.profile = aiProfile.value;
          init = { ...init, body: JSON.stringify(payload) };
        } catch (_error) {
          // Leave malformed/non-JSON requests untouched; the server remains the
          // authoritative validator and will report the request error normally.
        }
      }
    }
    return nativeFetch(input, init);
  };
})();
