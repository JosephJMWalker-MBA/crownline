(() => {
  const button = document.querySelector('#export-play-record');
  if (!button) return;

  const defaultLabel = button.textContent;

  function filenameStamp() {
    return new Date().toISOString().replace(/[:.]/g, '-');
  }

  button.addEventListener('click', async () => {
    button.disabled = true;
    button.textContent = 'Preparing export…';
    try {
      const response = await fetch('/api/export', { cache: 'no-store' });
      if (!response.ok) {
        const message = await response.text();
        throw new Error(message || `Export failed (${response.status})`);
      }

      const payload = await response.json();
      const blob = new Blob(
        [`${JSON.stringify(payload, null, 2)}\n`],
        { type: 'application/json' }
      );
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `crownline-play-record-${filenameStamp()}.json`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);

      const humanMoves = payload.summary?.human_moves_recorded ?? 0;
      button.textContent = `Exported ${humanMoves} human moves`;
      window.setTimeout(() => {
        button.textContent = defaultLabel;
      }, 1800);
    } catch (error) {
      console.error('Crownline play-record export failed', error);
      button.textContent = 'Export failed';
      window.setTimeout(() => {
        button.textContent = defaultLabel;
      }, 2200);
    } finally {
      button.disabled = false;
    }
  });
})();
