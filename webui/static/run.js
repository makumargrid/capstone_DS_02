/* ═══════════════════════════════════════════════════════════════════════════
   run.js — Run page: WebSocket-first live updates, HTTP poll fallback,
   Q&A handling, spec table, plan preview, results, certificate, report,
   handoff bundle, state timeline.
   ═══════════════════════════════════════════════════════════════════════════ */

const RID = new URLSearchParams(window.location.search).get('rid');
if (!RID) { document.body.innerHTML = '<p style="text-align:center;padding:40px">No run ID provided.</p>'; throw new Error('No RID'); }
document.getElementById('rid-display').textContent = RID;

const STAGES = ['intent', 'plan', 'compile', 'inspect', 'review', 'done'];
let lastState = 'queued';
let seenArtifacts = new Set();
let _originalTitle = document.title;
let _titleFlashInterval = null;
let ws = null;
let wsConnected = false;
let wsReconnectTimer = null;
let _timelineEntries = [];

// ── Progress ──────────────────────────────────────────────────────────────
function setProgress(stage) {
  const idx = STAGES.indexOf(stage);
  document.querySelectorAll('.progress-step').forEach((el, i) => {
    el.className = 'progress-step';
    if (stage === 'failed') {
      el.classList.add('failed');
    } else if (stage === 'done') {
      el.classList.add('done');
    } else {
      if (i < idx) el.classList.add('done');
      else if (i === idx) el.classList.add('active');
    }
  });
}

// ── Trust Badge ───────────────────────────────────────────────────────────
function setTrustBadge(trustLabel) {
  const el = document.getElementById('trust-badge');
  el.style.display = 'inline-flex';
  if (trustLabel === 'requires_review' || trustLabel === 'requires review') {
    el.className = 'trust-badge requires-review';
    el.textContent = '⚠️ Requires Human Review';
  } else if (trustLabel === 'flagged' || trustLabel === 'failed_verification') {
    el.className = 'trust-badge flagged';
    el.textContent = '🚩 Flagged';
  } else {
    el.className = 'trust-badge certified';
    el.textContent = '✅ Certified';
  }
}

// ── Title Flash (tab notification) ────────────────────────────────────────
function startTitleFlash(msg) {
  stopTitleFlash();
  let on = true;
  _titleFlashInterval = setInterval(() => {
    document.title = on ? `❓ ${msg}` : _originalTitle;
    on = !on;
  }, 1000);
}

function stopTitleFlash() {
  if (_titleFlashInterval) { clearInterval(_titleFlashInterval); _titleFlashInterval = null; }
  document.title = _originalTitle;
}

// ── State Timeline ────────────────────────────────────────────────────────
function addTimelineEntry(text, className) {
  // Avoid duplicate entries
  const lastEntry = _timelineEntries[_timelineEntries.length - 1];
  if (lastEntry && lastEntry.text === text) return;

  // Demote previous entry
  const container = document.getElementById('state-timeline');
  const existing = container.querySelectorAll('.timeline-entry');
  existing.forEach(e => {
    e.classList.remove('active', 'waiting');
    e.classList.add('done');
  });

  const entry = document.createElement('div');
  entry.className = `timeline-entry ${className || 'active'}`;
  entry.innerHTML = `
    <span class="timeline-dot"></span>
    <span class="timeline-text">${text}</span>
    <span class="timeline-time">${new Date().toLocaleTimeString()}</span>
  `;
  container.appendChild(entry);
  _timelineEntries.push({ text, className, time: Date.now() });
  // Auto-scroll
  container.scrollTop = container.scrollHeight;
}

// ── WebSocket Indicator ───────────────────────────────────────────────────
function setWsStatus(status) {
  const dot = document.getElementById('ws-dot');
  const label = document.getElementById('ws-label');
  dot.className = 'ws-dot ' + status;
  const labels = { connected: 'Live', disconnected: 'Polling', connecting: 'Connecting…' };
  label.textContent = labels[status] || status;
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

// ── Handoff Bundle ────────────────────────────────────────────────────────
function renderHandoff(manifest) {
  if (!manifest) return '<p style="color:var(--text-muted)">No handoff bundle available.</p>';
  const trustClass = manifest.trust_label === 'certified' ? 'pass' : 'fail';
  const trustText = {
    certified: '✅ Certified',
    requires_review: '⚠️ Requires Review',
    failed_verification: '❌ Failed'
  }[manifest.trust_label] || manifest.trust_label;

  let html = `<div class="handoff-grid">
    <div class="handoff-item"><h4>Trust Label</h4><div class="value ${trustClass}">${trustText}</div></div>
    <div class="handoff-item"><h4>Geometry Valid</h4><div class="value ${manifest.geometrically_valid ? 'pass' : 'fail'}">${manifest.geometrically_valid ? '✅ Yes' : '❌ No'}</div></div>
    <div class="handoff-item"><h4>Manufacturable</h4><div class="value ${manifest.manufacturable ? 'pass' : 'fail'}">${manifest.manufacturable ? '✅ Yes' : '❌ No'}</div></div>
    <div class="handoff-item"><h4>Nodes</h4><div class="value">${(manifest.nodes || []).length} features</div></div>
  </div>`;

  // Download links
  html += '<div class="action-bar" style="margin-top:12px">';
  if (manifest.files) {
    if (manifest.files.stl) html += `<a class="btn btn-outline btn-sm" href="/designs/${RID}/artifacts/forgecad_handoff/${manifest.files.stl}">⬇ STL</a>`;
    if (manifest.files.step) html += `<a class="btn btn-outline btn-sm" href="/designs/${RID}/artifacts/forgecad_handoff/${manifest.files.step}">⬇ STEP</a>`;
    if (manifest.files.ir) html += `<a class="btn btn-outline btn-sm" href="/designs/${RID}/artifacts/forgecad_handoff/${manifest.files.ir}">⬇ IR JSON</a>`;
  }
  html += '</div>';
  return html;
}

// ── Q&A Handler ───────────────────────────────────────────────────────────
let _qaEventsBound = false;
let _qaImagePickBound = false;
let _lastQuestionId = null;

function handleQuestion(pq, state) {
  const qaCard = document.getElementById('qa-card');

  if (state === 'waiting_for_user' && pq) {
    // Don't re-render the same question
    if (_lastQuestionId === pq.id) return;
    _lastQuestionId = pq.id;

    const qText = pq.question || '';
    const isImagePick = qText.startsWith('<<<IMAGE_PICK>>>');

    if (isImagePick) {
      // Image pick mode: parse candidate URLs and render thumbnails
      const bodyText = qText.replace('<<<IMAGE_PICK>>>', '').trim();
      const urlRegex = /\[([^\]]+)\]\(([^)]+)\)/g;
      let match;
      const candidates = [];
      while ((match = urlRegex.exec(bodyText)) !== null) {
        candidates.push({ title: match[1], url: match[2] });
      }
      const instructionText = bodyText.replace(urlRegex, '$1').trim();
      document.getElementById('qa-question').textContent = instructionText;
      document.getElementById('qa-text-group').style.display = 'none';
      document.getElementById('qa-quick-actions').style.display = 'none';

      let thumbHtml = '<div class="image-pick-grid" style="display:flex;flex-wrap:wrap;gap:12px;margin-top:12px">';
      candidates.forEach((c, i) => {
        thumbHtml += `<div class="image-pick-item" style="cursor:pointer;border:2px solid var(--slate-200);border-radius:8px;overflow:hidden;text-align:center;max-width:180px" data-pick="${i + 1}">
          <img src="${c.url}" alt="${c.title}" style="width:100%;height:120px;object-fit:cover;display:block" onerror="this.parentElement.style.display='none'">
          <span style="display:block;padding:4px 8px;font-size:12px;color:var(--text-muted)">${i + 1}. ${c.title}</span>
        </div>`;
      });
      thumbHtml += `<div class="image-pick-item image-pick-skip" style="cursor:pointer;border:2px dashed var(--slate-200);border-radius:8px;display:flex;align-items:center;justify-content:center;width:120px;height:120px" data-pick="skip">
        <span style="color:var(--text-muted);font-size:14px">Skip →</span>
      </div>`;
      thumbHtml += '</div>';
      document.getElementById('qa-question').innerHTML = instructionText + thumbHtml;

      if (!_qaImagePickBound) {
        _qaImagePickBound = true;
        qaCard.addEventListener('click', function (e) {
          const item = e.target.closest('.image-pick-item');
          if (!item) return;
          const pickValue = item.dataset.pick;
          if (!pickValue) return;
          const currentQid = qaCard.dataset.questionId;
          fetch(`/designs/${RID}/answer`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ question_id: currentQid, answer: pickValue })
          }).then(r => {
            if (r.ok) { qaCard.style.display = 'none'; stopTitleFlash(); _lastQuestionId = null; }
          }).catch(() => { });
        });
      }
    } else {
      // Standard Q&A mode
      document.getElementById('qa-question').textContent = qText;
      document.getElementById('qa-text-group').style.display = 'block';

      const text = qText.toLowerCase();
      const quickActions = document.getElementById('qa-quick-actions');
      const yesBtn = document.getElementById('btn-qa-yes');
      const noBtn = document.getElementById('btn-qa-no');

      if (text.includes('confirm') || text.includes('yes/no') || text.includes('yes / edit / no') || text.includes('approve') || text.includes('proposed design') || text.includes('proceed')) {
        quickActions.style.display = 'flex';
        if (text.includes('approve') || text.includes('proposed design')) {
          yesBtn.textContent = '✅ Approve Plan';
          noBtn.textContent = '❌ Reject / Halt';
        } else {
          yesBtn.textContent = 'Yes / Confirm';
          noBtn.textContent = 'No / Cancel';
        }
      } else {
        quickActions.style.display = 'none';
      }
    }

    qaCard.style.display = 'block';
    qaCard.dataset.questionId = pq.id;
    if (!isImagePick) {
      document.getElementById('qa-text-group').style.display = 'block';
    }

    // Flash tab title
    startTitleFlash('Question — respond now');
    addTimelineEntry('⏳ Waiting for your response…', 'waiting');

    // Scroll Q&A card into view
    qaCard.scrollIntoView({ behavior: 'smooth', block: 'center' });

    // Bind event handlers once
    if (!_qaEventsBound) {
      _qaEventsBound = true;
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
            stopTitleFlash();
            _lastQuestionId = null;
            addTimelineEntry(`✅ Answered: "${ansText.substring(0, 60)}${ansText.length > 60 ? '…' : ''}"`, 'done');
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
    stopTitleFlash();
  }
}

// ── Process a status frame (from WS or HTTP) ──────────────────────────────
async function processFrame(status) {
  const state = status.state || 'queued';
  const artifacts = status.artifacts || [];
  const phase = status.phase || null;

  // Timeline updates based on state transitions
  if (state !== lastState) {
    const labels = {
      queued: '📋 Queued — waiting to start',
      running: '🔧 Running — pipeline active',
      waiting_for_user: '⏳ Waiting for your response',
      approved: '✅ Approved — design certified',
      completed: '✅ Completed',
      failed: '❌ Failed'
    };
    addTimelineEntry(labels[state] || state, state === 'failed' ? 'error' : state === 'waiting_for_user' ? 'waiting' : 'active');
  }

  // Error display
  if (state === 'failed') {
    const errorCard = document.getElementById('error-card');
    errorCard.style.display = 'block';
    document.getElementById('error-message').textContent = status.error || 'Pipeline failed. Check the log for details.';
  }

  // Progress bar
  if (phase) {
    setProgress(phase);
  } else {
    if (state === 'approved' || state === 'completed') setProgress('done');
    else if (state === 'failed') setProgress('failed');
    else if (state === 'running') {
      if (artifacts.some(a => a.includes('reviewer_verdict'))) setProgress('review');
      else if (artifacts.some(a => a.includes('solid_inspection'))) setProgress('inspect');
      else if (artifacts.some(a => a.includes('model.stl'))) setProgress('compile');
      else if (artifacts.some(a => a.includes('ir.json'))) setProgress('plan');
      else setProgress('intent');
    }
  }

  // Q&A handling
  handleQuestion(status.pending_question, state);

  // Manifest (trust badge + certificate)
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

  // Spec
  if (artifacts.includes('01b_spec.json') && !seenArtifacts.has('spec')) {
    try {
      const spec = await fetch(`/designs/${RID}/artifacts/01b_spec.json`).then(r => r.json());
      document.getElementById('spec-content').innerHTML = renderSpec(spec);
      document.getElementById('spec-card').style.display = 'block';
      addTimelineEntry('📋 Spec extracted and grounded', 'done');
    } catch (e) { /* not ready */ }
    seenArtifacts.add('spec');
  }

  // Plan preview — show IR explanation when available
  if (artifacts.some(a => a.includes('ir.json')) && !seenArtifacts.has('ir')) {
    try {
      // Find the latest ir.json file (pick the last numbered one)
      const irFiles = artifacts.filter(a => a.includes('ir.json') && a.startsWith('03_'));
      const irFile = irFiles.length > 0 ? irFiles[irFiles.length - 1] : 'ir.json';
      const ir = await fetch(`/designs/${RID}/artifacts/${irFile}`).then(r => r.json());
      if (ir && ir.features) {
        document.getElementById('plan-explanation').textContent =
          `Design: ${ir.features.length} features, envelope ${ir.envelope?.x_mm}×${ir.envelope?.y_mm}×${ir.envelope?.z_mm}mm.`;
      }
      document.getElementById('preview-card').style.display = 'block';
      addTimelineEntry(`🎨 IR generated — ${ir?.features?.length || '?'} features`, 'done');
    } catch (e) { /* not ready */ }
    seenArtifacts.add('ir');
  }

  // View images (only pick the latest iteration's views)
  const viewFiles = artifacts.filter(a => a.startsWith('09_') && a.endsWith('.png'));
  if (viewFiles.length > 0 && !seenArtifacts.has('views')) {
    // Get the latest prefix (e.g. "09_outer5")
    const lastView = viewFiles[viewFiles.length - 1];
    const prefix = lastView.split('_view_')[0] || lastView.split('_assembly_')[0];
    const latestViews = viewFiles.filter(f => f.startsWith(prefix));
    const imgs = latestViews.map(f => `<img src="/designs/${RID}/artifacts/${f}" alt="${f}">`).join('');
    document.getElementById('preview-images').innerHTML = imgs || '<p>No preview images</p>';
    document.getElementById('btn-approve').disabled = false;
    document.getElementById('btn-refine').disabled = false;
    seenArtifacts.add('views');
    addTimelineEntry('🖼 Multi-view renders ready', 'done');
  }

  // Results (L2 inspection)
  const inspFiles = artifacts.filter(a => a.includes('solid_inspection.json') || a.includes('assembly_inspection.json'));
  if (inspFiles.length > 0 && !seenArtifacts.has('inspect')) {
    try {
      const latestInsp = inspFiles[inspFiles.length - 1];
      const l2 = await fetch(`/designs/${RID}/artifacts/${latestInsp}`).then(r => r.json());
      document.getElementById('checks-container').innerHTML = renderChecks(l2.checks);
      document.getElementById('results-card').style.display = 'block';
      addTimelineEntry(`📊 L2 inspection — ${l2.valid ? 'passed' : l2.hard_failures?.length + ' failure(s)'}`, l2.valid ? 'done' : 'error');
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
  if (artifacts.some(a => a.endsWith('_ir.json') && a.startsWith('03_'))) {
    const irFile = artifacts.filter(a => a.endsWith('_ir.json') && a.startsWith('03_')).pop();
    if (irFile) {
      const el = document.getElementById('download-ir');
      el.href = `/designs/${RID}/artifacts/${irFile}`;
      el.style.display = 'inline-flex';
    }
  }

  // Report card
  const reportUrl = status.report_url || (artifacts.includes('report.html') ? `/designs/${RID}/report` : null);
  if (reportUrl && !seenArtifacts.has('report')) {
    const reportCard = document.getElementById('report-card');
    reportCard.style.display = 'block';
    document.getElementById('report-link').href = reportUrl;
    document.getElementById('report-iframe').src = reportUrl;
    seenArtifacts.add('report');
    addTimelineEntry('📄 Run report generated', 'done');
  }

  // Handoff bundle
  if (artifacts.includes('forgecad_handoff') && !seenArtifacts.has('handoff')) {
    try {
      const hm = await fetch(`/designs/${RID}/artifacts/forgecad_handoff/manifest.json`).then(r => r.json());
      document.getElementById('handoff-content').innerHTML = renderHandoff(hm);
      document.getElementById('handoff-card').style.display = 'block';
      setTrustBadge(hm.trust_label);
      seenArtifacts.add('handoff');
      addTimelineEntry(`📦 Handoff bundle — ${hm.trust_label}`, hm.trust_label === 'certified' ? 'done' : 'error');
    } catch (e) { /* not ready — might be a directory, try via manifest.json path */ }
  }

  // Log
  try {
    const logResp = await fetch(`/designs/${RID}/log`);
    const logData = await logResp.json();
    const logEl = document.getElementById('log-output');
    logEl.textContent = logData.log || 'No log data';
    logEl.scrollTop = logEl.scrollHeight;
  } catch (e) { /* log not available */ }

  // Final Acceptance Card
  const acceptanceCard = document.getElementById('acceptance-card');
  if ((state === 'approved' || state === 'completed') && acceptanceCard) {
    if (artifacts.includes('10_acceptance_record.json')) {
      if (!window.acceptanceRecordLoaded) {
        window.acceptanceRecordLoaded = true;
        try {
          const rec = await fetch(`/designs/${RID}/artifacts/10_acceptance_record.json`).then(r => r.json());
          const contentEl = document.getElementById('acceptance-content');
          if (rec.accepted === true) {
            contentEl.innerHTML = `
              <div style="background: #e6f4ea; color: #137333; padding: 16px; border-radius: 8px; border: 1px solid #ceead6; margin-top: 8px">
                <strong>✅ Accepted:</strong> This design has been approved and signed off.
                ${rec.note ? `<p style="margin-top:8px;font-style:italic">Feedback: "${rec.note}"</p>` : ''}
              </div>
            `;
          } else {
            contentEl.innerHTML = `
              <div style="background: #fce8e6; color: #c5221f; padding: 16px; border-radius: 8px; border: 1px solid #fad2cf; margin-top: 8px">
                <strong>❌ Rejected:</strong> This design was rejected or a revision was requested.
                ${rec.note ? `<p style="margin-top:8px;font-style:italic">Feedback: "${rec.note}"</p>` : ''}
              </div>
              <div style="margin-top: 12px">
                <button class="btn btn-primary btn-sm" id="btn-re-iterate">🔄 Request Revision</button>
              </div>
            `;
            document.getElementById('btn-re-iterate').onclick = () => {
              const fb = prompt("Enter additional revision instructions if needed:", rec.note || "");
              if (fb !== null) {
                startIteration(fb);
              }
            };
          }
          acceptanceCard.style.display = 'block';
        } catch (e) {
          window.acceptanceRecordLoaded = false;
        }
      }
    } else {
      const contentEl = document.getElementById('acceptance-content');
      if (contentEl && !contentEl.querySelector('#btn-accept-design')) {
        contentEl.innerHTML = `
          <p style="color:var(--text-muted);margin-bottom:12px;font-size:14px">Please review the 3D model and verification checks. Do you accept this design?</p>
          <div class="form-group">
            <label for="accept-note">Revision Feedback / Sign-off Comments (optional):</label>
            <textarea class="form-control" id="accept-note" placeholder="Add comments, or describe requested changes if rejecting..."></textarea>
          </div>
          <div class="action-bar" style="margin-top:12px">
            <button class="btn btn-success" id="btn-accept-design">Accept & Sign-off</button>
            <button class="btn btn-danger" id="btn-reject-design">Reject & Request Revision</button>
          </div>
        `;
        acceptanceCard.style.display = 'block';

        document.getElementById('btn-accept-design').onclick = async () => {
          const note = document.getElementById('accept-note').value.trim();
          await submitAcceptance(true, note);
        };

        document.getElementById('btn-reject-design').onclick = async () => {
          const note = document.getElementById('accept-note').value.trim();
          if (!note) {
            alert('Please describe the reason for rejection / what needs to be changed.');
            return;
          }
          await submitAcceptance(false, note);
        };
      }
    }
  } else if (acceptanceCard) {
    acceptanceCard.style.display = 'none';
    window.acceptanceRecordLoaded = false;
  }

  lastState = state;
}


// ── WebSocket Connection ──────────────────────────────────────────────────
function connectWs() {
  if (ws && (ws.readyState === WebSocket.CONNECTING || ws.readyState === WebSocket.OPEN)) return;

  setWsStatus('connecting');
  const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  ws = new WebSocket(`${proto}//${window.location.host}/ws/designs/${RID}/stream`);

  ws.onopen = () => {
    wsConnected = true;
    setWsStatus('connected');
    console.log('[WS] Connected to live stream');
  };

  ws.onmessage = async (event) => {
    try {
      const frame = JSON.parse(event.data);
      if (frame.error) {
        console.error('[WS] Server error:', frame.error);
        return;
      }
      await processFrame(frame);
    } catch (e) {
      console.error('[WS] Frame parse error:', e);
    }
  };

  ws.onclose = () => {
    wsConnected = false;
    setWsStatus('disconnected');
    console.log('[WS] Disconnected — falling back to HTTP poll');
    // Auto-reconnect if the run is still active
    if (lastState !== 'approved' && lastState !== 'completed' && lastState !== 'failed') {
      wsReconnectTimer = setTimeout(connectWs, 3000);
    }
  };

  ws.onerror = (e) => {
    console.error('[WS] Error:', e);
    wsConnected = false;
    setWsStatus('disconnected');
  };
}


// ── HTTP Poll (fallback) ──────────────────────────────────────────────────
async function poll() {
  // Skip if WS is delivering live updates (except for log which WS doesn't send)
  if (wsConnected && lastState !== 'approved' && lastState !== 'completed' && lastState !== 'failed') {
    // Still fetch log via HTTP since WS doesn't stream it
    try {
      const logResp = await fetch(`/designs/${RID}/log`);
      const logData = await logResp.json();
      const logEl = document.getElementById('log-output');
      logEl.textContent = logData.log || 'No log data';
      logEl.scrollTop = logEl.scrollHeight;
    } catch (e) { }
    return;
  }

  try {
    const resp = await fetch(`/designs/${RID}/status`);
    const status = await resp.json();
    await processFrame(status);
  } catch (e) {
    console.error('Poll error:', e);
  }
}


// ── Acceptance & Iteration ────────────────────────────────────────────────
async function submitAcceptance(accepted, note) {
  try {
    const res = await fetch(`/designs/${RID}/approve`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ accepted, note })
    });
    if (res.ok) {
      window.acceptanceRecordLoaded = false;
      if (!accepted) {
        if (confirm("Design rejected. Would you like to start a new revision run seeded with this feedback?")) {
          await startIteration(note);
        }
      }
      poll();
    } else {
      const err = await res.json();
      alert('Failed: ' + (err.detail || 'Unknown error'));
    }
  } catch (e) {
    alert('Error submitting acceptance: ' + e);
  }
}

async function startIteration(feedback) {
  try {
    const res = await fetch(`/designs/${RID}/iterate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ feedback })
    });
    if (res.ok) {
      const data = await res.json();
      if (data.run_id) {
        window.location.href = `/ui/run.html?rid=${data.run_id}`;
      } else {
        alert('Failed to start iteration.');
      }
    } else {
      const err = await res.json();
      alert('Failed: ' + (err.detail || 'Unknown error'));
    }
  } catch (e) {
    alert('Error starting iteration: ' + e);
  }
}

// ── Boot ──────────────────────────────────────────────────────────────────
// Set initial timestamp
const startEl = document.getElementById('timeline-start');
if (startEl) startEl.textContent = new Date().toLocaleTimeString();

// Connect WebSocket (primary) + start HTTP poll (fallback)
connectWs();
poll();
setInterval(poll, 3000);