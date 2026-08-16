const tracker = document.querySelector('#crownline-tracker');

function lineFromRow(row) {
  return (row?.title || '')
    .split(' · ')
    .map((square) => square.trim())
    .filter(Boolean);
}

function preview(line = null) {
  window.dispatchEvent(new CustomEvent('crownline-preview-line', {
    detail: { line },
  }));
}

tracker?.addEventListener('pointerover', (event) => {
  const row = event.target.closest?.('.tracker-item');
  if (!row || !tracker.contains(row)) return;
  const from = event.relatedTarget?.closest?.('.tracker-item');
  if (from === row) return;
  const line = lineFromRow(row);
  if (line.length === 3) preview(line);
});

tracker?.addEventListener('pointerout', (event) => {
  const row = event.target.closest?.('.tracker-item');
  if (!row || !tracker.contains(row)) return;
  const to = event.relatedTarget?.closest?.('.tracker-item');
  if (to === row) return;
  preview(null);
});

tracker?.addEventListener('focusin', (event) => {
  const row = event.target.closest?.('.tracker-item');
  const line = lineFromRow(row);
  if (line.length === 3) preview(line);
});

tracker?.addEventListener('focusout', () => preview(null));
