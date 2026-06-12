/* ═══════════════════════════════════════════════════════════════════════════
   app.js — Dashboard: intake form, image upload, run list.
   ═══════════════════════════════════════════════════════════════════════════ */

document.addEventListener('DOMContentLoaded', () => {
  const form = document.getElementById('design-form');
  const submitBtn = document.getElementById('submit-btn');
  const runList = document.getElementById('run-list-container');
  const uploadZone = document.getElementById('upload-zone');
  const imageInput = document.getElementById('image-input');
  const uploadText = document.getElementById('upload-text');
  const uploadPreview = document.getElementById('upload-preview');

  // ── Image Upload ─────────────────────────────────────────────────────
  uploadZone.addEventListener('click', () => imageInput.click());
  uploadZone.addEventListener('dragover', e => { e.preventDefault(); uploadZone.classList.add('drag-over'); });
  uploadZone.addEventListener('dragleave', () => uploadZone.classList.remove('drag-over'));
  uploadZone.addEventListener('drop', e => {
    e.preventDefault();
    uploadZone.classList.remove('drag-over');
    if (e.dataTransfer.files.length) {
      imageInput.files = e.dataTransfer.files;
      showPreview(e.dataTransfer.files[0]);
    }
  });
  imageInput.addEventListener('change', () => {
    if (imageInput.files.length) showPreview(imageInput.files[0]);
  });

  function showPreview(file) {
    const reader = new FileReader();
    reader.onload = e => {
      uploadPreview.src = e.target.result;
      uploadPreview.style.display = 'block';
      uploadText.textContent = '📷 Image ready — will be used for shape matching';
      uploadZone.classList.add('has-image');
    };
    reader.readAsDataURL(file);
  }

  // ── Form Submit ──────────────────────────────────────────────────────
  form.addEventListener('submit', async e => {
    e.preventDefault();
    const prompt = document.getElementById('prompt').value;
    const process = document.getElementById('process').value;

    if (!prompt.trim()) {
      alert('Please describe what you want to create.');
      return;
    }

    submitBtn.disabled = true;
    submitBtn.textContent = '⏳ Starting…';

    try {
      const resp = await fetch('/designs', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          prompt: prompt.trim(),
          process: process || undefined,
          interactive: true,
        }),
      });
      const data = await resp.json();
      if (data.run_id) {
        window.location.href = `/ui/run.html?rid=${data.run_id}`;
      } else {
        alert('Failed to start. Check the API is running.');
      }
    } catch (err) {
      alert('Could not connect to the API. Is the server running?');
    } finally {
      submitBtn.disabled = false;
      submitBtn.textContent = '🚀 Start Design';
    }
  });

  // ── Poll Run List ────────────────────────────────────────────────────
  async function loadRuns() {
    try {
      const resp = await fetch('/designs');
      const data = await resp.json();
      const runs = data.runs || [];
      if (runs.length === 0) {
        runList.innerHTML = '<p style="color:var(--text-muted)">No designs yet — create your first one above!</p>';
        return;
      }
      runList.innerHTML = '<ul class="run-list">' + runs.map(r => {
        const stateClass = { approved: 'passed', completed: 'passed', failed: 'failed', queued: 'pending', running: 'running' }[r.state] || 'pending';
        return `<li class="run-item">
                    <span class="status-dot ${stateClass}"></span>
                    <a href="/ui/run.html?rid=${r.run_id}">${r.prompt || '(no prompt)'}</a>
                    <span class="run-state">${r.state}</span>
                </li>`;
      }).join('') + '</ul>';
    } catch (err) {
      runList.innerHTML = '<p style="color:var(--danger)">Could not load runs.</p>';
    }
  }

  loadRuns();
  setInterval(loadRuns, 3000);
});