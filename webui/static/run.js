/* ═══════════════════════════════════════════════════════════════════════════
   run.js — Run page: status polling, spec table, plan preview, results, certificate.
   ═══════════════════════════════════════════════════════════════════════════ */

const RID = new URLSearchParams(window.location.search).get('rid');
if (!RID) { document.body.innerHTML = '<p style="text-align:center;padding:40px">No run ID provided.</p>'; throw new Error('No RID'); }
document.getElementById('rid-display').textContent = RID;

const STAGES = ['intent', 'plan', 'compile', 'inspect', 'review', 'done'];
let lastState = 'queued';
let seenArtifacts = new Set();

// ── Progress ──────────────────────────────────────────────────────────────
function setProgress(stage) {
  const idx = STAGES.indexOf(stage);
  document.querySelectorAll('.progress-step').forEach((el, i) => {
    el.className = 'progress-step';
    if (i < idx) el.classList.add('done');
    else if (i === idx) el.classList.add('active');
  });
  if (stage === 'done') {
    document.querySelectorAll('.progress-step').forEach(el => el.className = 'progress-step done');
  }
}

// ── Trust Badge ───────────────────────────────────────────────────────────
function setTrustBadge(trustLabel) {
  const el = document.getElementById('trust-badge');
  el.style.display = 'inline-flex';
  if (trustLabel === 'requires_review' || trustLabel === 'requires review') {
    el.className = 'trust-badge requires-review';
    el.textContent = '⚠️ Requires Human Review';
  } else if (trustLabel === 'flagged') {
    el.className = 'trust-badge flagged';
    el.textContent = '🚩 Flagged';
  } else {
    el.className = 'trust-badge certified';
    el.textContent = '✅ Certified';
  }
}

// ── Spec Table ────────────────────────────────────────────────────────────
function renderSpec(spec) {
  if (!spec || !spec.length) return '<p style="color:var(--text-muted)">No specification available.</p>';
  let html = '<table class="spec-table"><tr><th>Requirement</th><th>Value</th><th>Standard</th></tr>';
  spec.forEach(r => {
    const val = r.expected != null ? r.expected : r.description || '—';
    const src = r.source || '';
    html += `<tr><td>${r.description || r.claim + ': ' + r.target}</td><td><strong>${val}</strong></td><td class="source-citation">${src ? '↗ ' + src : ''}</td></tr>`;
  });
  html += '</table>';
  return html;
}

// ── Checks ────────────────────────────────────────────────────────────────
function renderChecks(checks) {
  if (!checks || !checks.length) return '<p style="color:var(--text-muted)">No check results yet.</p>';
  return checks.map(c => {
    const icon = c.passed ? '<span class="check-icon check-pass">✅</span>' : '<span class="check-icon check-fail">❌</span>';
    const detail = c.detail ? ` — ${c.detail}` : '';
    return `<div class="check-row">${icon} <strong>${c.node}.${c.claim}</strong>: ${c.measured} ${c.expected ? '(expected ' + c.expected + ')' : ''}${detail}</div>`;
  }).join('');
}

// ── Certificate ───────────────────────────────────────────────────────────
function renderCert(certificate, trustLabel) {
  if (!certificate) return '<p style="color:var(--text-muted)">No certificate available.</p>';
  let html = '<p style="margin-bottom:8px">';
  html += `<span class="trust-badge ${trustLabel === 'certified' ? 'certified' : 'requires-review'}">`;
  html += trustLabel === 'certified' ? '✅ Certified' : '⚠️ Requires Human Review';
  html += '</span></p>';
  html += '<table class="spec-table"><tr><th>Check</th><th>Result</th><th>Count</th></tr>';
  (certificate.checks || []).forEach(c => {
    html += `<tr><td>${c.check}</td><td>${c.passed ? '✅ Pass' : '❌ Fail'}</td><td>${c.count}</td></tr>`;
  });
  html += '</table>';
  if (certificate.standards_used) html += `<p style="margin-top:8px;color:var(--success);font-size:12px">Standards: ${certificate.standards_used.join(', ')}</p>`;
  if (certificate.meshlib_battery) html += `<p style="color:var(--text-muted);font-size:12px">MeshLib deterministic battery ✓</p>`;
  return html;
}

// ── Main Poll Loop ────────────────────────────────────────────────────────
async function poll() {
  try {
    const resp = await fetch(`/designs/${RID}/status`);
    const status = await resp.json();
    const state = status.state || 'queued';
    const artifacts = status.artifacts || [];

    // Update trust badge from manifest
    if (artifacts.includes('manifest.json') && !seenArtifacts.has('manifest')) {
      try {
        const mf = await fetch(`/designs/${RID}/artifacts/manifest.json`).then(r => r.json());
        if (mf.trust_label) setTrustBadge(mf.trust_label);
        if (mf.certificate) document.getElementById('cert-content').innerHTML = renderCert(mf.certificate, mf.trust_label);
        document.getElementById('cert-card').style.display = 'block';
        if (mf.requires_review) setTrustBadge('requires_review');
      } catch (e) { /* manifest not ready yet */ }
      seenArtifacts.add('manifest');
    }

    // Progress
    if (state === 'approved' || state === 'completed') setProgress('done');
    else if (state === 'running') {
      if (artifacts.some(a => a.includes('reviewer_verdict'))) setProgress('review');
      else if (artifacts.some(a => a.includes('solid_inspection'))) setProgress('inspect');
      else if (artifacts.some(a => a.includes('model.stl'))) setProgress('compile');
      else if (artifacts.some(a => a.includes('ir.json'))) setProgress('plan');
      else setProgress('intent');
    }
    // Clarification Q&A
    const qaCard = document.getElementById('qa-card');
    const pq = status.pending_question;
    if (pq) {
      document.getElementById('qa-question').textContent = pq.question;
      qaCard.style.display = 'block';
      qaCard.dataset.questionId = pq.id;
      
      const text = pq.question.toLowerCase();
      const quickActions = document.getElementById('qa-quick-actions');
      if (text.includes('confirm') || text.includes('yes/no') || text.includes('yes / edit / no')) {
        quickActions.style.display = 'flex';
      } else {
        quickActions.style.display = 'none';
      }

      if (!window.qaEventHandlersBound) {
        window.qaEventHandlersBound = true;
        const submitBtn = document.getElementById('btn-qa-submit');
        const inputField = document.getElementById('qa-input');
        
        async function sendAnswer(ansText) {
          submitBtn.disabled = true;
          const currentQid = qaCard.dataset.questionId;
          try {
            const res = await fetch(`/designs/${RID}/answer`, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ question_id: currentQid, answer: ansText })
            });
            if (res.ok) {
              qaCard.style.display = 'none';
              inputField.value = '';
              poll();
            } else {
              const err = await res.json();
              alert('Failed to submit: ' + (err.detail || 'Unknown error'));
            }
          } catch (e) {
            alert('Failed to submit answer: ' + e);
          } finally {
            submitBtn.disabled = false;
          }
        }

        submitBtn.onclick = () => {
          const ans = inputField.value.trim();
          if (!ans) { alert('Please type an answer before submitting.'); return; }
          sendAnswer(ans);
        };

        document.getElementById('btn-qa-yes').onclick = () => sendAnswer('yes');
        document.getElementById('btn-qa-no').onclick = () => sendAnswer('no');
      }
    } else {
      qaCard.style.display = 'none';
    }


    // Spec
    if (artifacts.includes('01b_spec.json') && !seenArtifacts.has('spec')) {
      try {
        const spec = await fetch(`/designs/${RID}/artifacts/01b_spec.json`).then(r => r.json());
        document.getElementById('spec-content').innerHTML = renderSpec(spec);
        document.getElementById('spec-card').style.display = 'block';
      } catch (e) { /* not ready */ }
      seenArtifacts.add('spec');
    }

    // Plan preview — show IR explanation when available
    if (artifacts.some(a => a.includes('ir.json')) && !seenArtifacts.has('ir')) {
      try {
        const ir = await fetch(`/designs/${RID}/artifacts/ir.json`).then(r => r.json());
        if (ir && ir.features) {
          document.getElementById('plan-explanation').textContent =
            `Design: ${ir.features.length} features, envelope ${ir.envelope?.x_mm}×${ir.envelope?.y_mm}×${ir.envelope?.z_mm}mm.`;
        }
        document.getElementById('preview-card').style.display = 'block';
      } catch (e) { /* not ready */ }
      seenArtifacts.add('ir');
    }

    // View images
    if (artifacts.some(a => a.startsWith('09_')) && !seenArtifacts.has('views')) {
      const viewFiles = artifacts.filter(a => a.startsWith('09_') && a.endsWith('.png'));
      const imgs = viewFiles.map(f => `<img src="/designs/${RID}/artifacts/${f}" alt="${f}">`).join('');
      document.getElementById('preview-images').innerHTML = imgs || '<p>No preview images</p>';
      document.getElementById('btn-approve').disabled = false;
      document.getElementById('btn-refine').disabled = false;
      seenArtifacts.add('views');
    }

    // Results
    if (artifacts.includes('05_outer1_solid_inspection.json') && !seenArtifacts.has('inspect')) {
      try {
        const l2 = await fetch(`/designs/${RID}/artifacts/05_outer1_solid_inspection.json`).then(r => r.json());
        document.getElementById('checks-container').innerHTML = renderChecks(l2.checks);
        document.getElementById('results-card').style.display = 'block';
      } catch (e) { /* not ready */ }
      seenArtifacts.add('inspect');
    }

    // Downloads
    if (artifacts.some(a => a.includes('model.stl'))) {
      const stl = artifacts.find(a => a.includes('.stl') && !a.includes('step'));
      const step = artifacts.find(a => a.includes('.step'));
      if (stl) { const el = document.getElementById('download-stl'); el.href = `/designs/${RID}/artifacts/${stl}`; el.style.display = 'inline-flex'; }
      if (step) { const el = document.getElementById('download-step'); el.href = `/designs/${RID}/artifacts/${step}`; el.style.display = 'inline-flex'; }
      const el = document.getElementById('viewer-link');
      el.href = `/designs/${RID}/viewer`;
      el.style.display = 'inline-flex';
    }
    if (artifacts.includes('ir.json')) {
      const el = document.getElementById('download-ir');
      el.href = `/designs/${RID}/artifacts/ir.json`;
      el.style.display = 'inline-flex';
    }

    // Log
    try {
      const logResp = await fetch(`/designs/${RID}/log`);
      const logData = await logResp.json();
      document.getElementById('log-output').textContent = logData.log || 'No log data';
    } catch (e) { /* log not available */ }

    lastState = state;
  } catch (e) {
    console.error('Poll error:', e);
  }
}

poll();
setInterval(poll, 2000);