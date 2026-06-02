"""
api/viewer.py — the ForgeCAD editable surface (Phase 5), a single self-contained page.

WHAT: viewer_html(run_id) returns an HTML page that (1) loads a run's handoff
      bundle (ir.json + model.stl), (2) renders the STL in 3D (three.js with an
      inlined minimal binary-STL parser — no CDN dependency for the loader),
      (3) lets the user EDIT the IR and hit Recompile → POST /recompile →
      re-render the new solid + show the deterministic verification checks.
      The IR JSON is the single editable source of truth crossing the JS/Python
      boundary (our handoff contract).
CALLED BY: api/app.py (GET /designs/{id}/viewer).
CALLS (from the browser): GET /designs/{id}/artifacts/forgecad_handoff/{ir.json,model.stl},
                          POST /recompile.

Changes vs original:
  - Removed CDN dependency for STLLoader (was silently failing when CDN was
    unavailable or returned wrong format). Replaced with an inlined ~30-line
    minimal binary-STL parser that directly creates THREE.BufferGeometry.
  - Added try-catch in show() — errors now surface in #msg instead of
    disappearing silently into the JS console.
  - Added geometry validation (empty geometry shows a warning, not blank screen).
  - Camera distance now computed from the mesh bounding-box diagonal, so the
    part always fills the viewport regardless of its size in mm.
  - Added simple mouse-drag orbit so the user can inspect from any angle
    instead of watching a fixed auto-rotate that may leave the part off-screen.
"""
from __future__ import annotations


def viewer_html(run_id: str) -> str:
    return r"""<!doctype html><meta charset=utf-8><title>ForgeCAD — __RID__</title>
<style>
 body{margin:0;font:13px system-ui;display:flex;height:100vh;color:#111;overflow:hidden}
 #view{flex:1;background:#eef1f4;cursor:grab;user-select:none}
 #view.dragging{cursor:grabbing}
 #side{width:440px;border-left:1px solid #ddd;display:flex;flex-direction:column;padding:12px;box-sizing:border-box;overflow-y:auto}
 h1{font-size:15px;margin:0 0 8px}
 textarea{flex:1;min-height:260px;font:12px ui-monospace;width:100%;box-sizing:border-box}
 button{margin:8px 0;padding:8px 14px;font-weight:600;cursor:pointer}
 .badge{display:inline-block;padding:2px 8px;border-radius:4px;color:#fff;font-weight:600}
 .ok{background:#1a9850}.bad{background:#c23a1f}
 table{border-collapse:collapse;width:100%;font-size:12px}td{border:1px solid #eee;padding:3px 6px}
 /* Parameter sliders */
 details#params{margin:6px 0;border:1px solid #ddd;border-radius:4px}
 details#params summary{padding:6px 10px;cursor:pointer;font-weight:600;font-size:12px;background:#f8f8f8;border-radius:4px;user-select:none}
 details#params summary:hover{background:#eef1f4}
 .param-row{display:flex;align-items:center;gap:6px;padding:3px 10px;border-bottom:1px solid #f0f0f0}
 .param-row:last-child{border-bottom:none}
 .param-label{flex:1;font-size:11px;color:#555;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
 .param-slider{flex:2;cursor:pointer}
 .param-num{width:56px;font:12px ui-monospace;border:1px solid #ddd;border-radius:3px;padding:1px 4px;text-align:right}
 tr.p td{background:#f1fbf3}tr.f td{background:#fdf1f1}
 #msg{font-size:12px;color:#555;margin-bottom:6px}
 #hint{font-size:11px;color:#999;margin-top:4px}
</style>
<div id=view></div>
<div id=side>
 <h1>ForgeCAD · run __RID__</h1>
 <div id=msg>loading…</div>
 <details id=params><summary>Parameter shortcuts ▾</summary><div id=param-list></div></details>
 <textarea id=ir spellcheck=false></textarea>
 <button id=recompile>Recompile &amp; re-verify</button>
 <button id=reset style="background:#f5f5f5;color:#555;font-weight:400;font-size:12px;padding:5px 10px">&#8635; Reset to original</button>
 <div>Result: <span id=verdict class=badge>—</span></div>
 <table id=checks></table>
 <div id=hint>Drag to orbit · Scroll to zoom</div>
</div>
<script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
<script>
// ── Minimal inlined binary-STL parser (replaces THREE.STLLoader CDN dep) ────
// Parses OCCT/CadQuery binary STL directly into THREE.BufferGeometry.
// Binary STL layout: 80-byte header | uint32 n_tri | n_tri × (12B normal + 3×12B vert + 2B attr)
function parseBinSTL(buf) {
  var dv = new DataView(buf);
  var n  = dv.getUint32(80, true);
  // Sanity-check: expected file size = 84 + n*50
  if (buf.byteLength < 84 + n * 50) {
    throw new Error('STL truncated (expected ' + (84+n*50) + ' bytes, got ' + buf.byteLength + ')');
  }
  var pos = new Float32Array(n * 9);
  var nor = new Float32Array(n * 9);
  for (var i = 0; i < n; i++) {
    var b  = 84 + i * 50;
    var nx = dv.getFloat32(b,    true);
    var ny = dv.getFloat32(b+4,  true);
    var nz = dv.getFloat32(b+8,  true);
    for (var j = 0; j < 3; j++) {
      var vb = b + 12 + j * 12;
      var pi = i * 9 + j * 3;
      pos[pi]   = dv.getFloat32(vb,   true);
      pos[pi+1] = dv.getFloat32(vb+4, true);
      pos[pi+2] = dv.getFloat32(vb+8, true);
      nor[pi] = nx; nor[pi+1] = ny; nor[pi+2] = nz;
    }
  }
  var g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.BufferAttribute(pos, 3));
  g.setAttribute('normal',   new THREE.BufferAttribute(nor, 3));
  return g;
}

// ── Scene setup ──────────────────────────────────────────────────────────────
var RID  = '__RID__';
var base = '/designs/' + RID + '/artifacts/forgecad_handoff/';
var scene, camera, renderer, mesh;
var _camDist = 200;  // updated after first model load

function init() {
  var el = document.getElementById('view');
  scene = new THREE.Scene();
  scene.background = new THREE.Color(0xeef1f4);

  camera = new THREE.PerspectiveCamera(45, el.clientWidth / el.clientHeight, 0.1, 20000);
  camera.up.set(0, 0, 1);

  renderer = new THREE.WebGLRenderer({ antialias: true });
  renderer.setPixelRatio(window.devicePixelRatio);
  renderer.setSize(el.clientWidth, el.clientHeight);
  el.appendChild(renderer.domElement);

  // Lighting
  scene.add(new THREE.HemisphereLight(0xffffff, 0x444466, 1.1));
  var d = new THREE.DirectionalLight(0xffffff, 0.6);
  d.position.set(1, -1, 1); scene.add(d);
  var d2 = new THREE.DirectionalLight(0xffffff, 0.3);
  d2.position.set(-1, 1, -0.5); scene.add(d2);

  // Orbit state
  var isDragging = false, lastX = 0, lastY = 0;
  var azimuth = Math.PI / 4, elevation = 0.4;

  el.addEventListener('mousedown', function(e) { isDragging = true; lastX = e.clientX; lastY = e.clientY; el.classList.add('dragging'); });
  window.addEventListener('mouseup',   function()  { isDragging = false; el.classList.remove('dragging'); });
  window.addEventListener('mousemove', function(e) {
    if (!isDragging) return;
    azimuth   += (e.clientX - lastX) * 0.01;
    elevation -= (e.clientY - lastY) * 0.01;
    elevation  = Math.max(-1.35, Math.min(1.35, elevation));
    lastX = e.clientX; lastY = e.clientY;
  });
  el.addEventListener('wheel', function(e) {
    _camDist *= e.deltaY > 0 ? 1.12 : 0.89;
    _camDist = Math.max(1, Math.min(50000, _camDist));
    e.preventDefault();
  }, { passive: false });

  // Resize
  window.addEventListener('resize', function() {
    camera.aspect = el.clientWidth / el.clientHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(el.clientWidth, el.clientHeight);
  });

  // Render loop (orbit on drag; auto-slow-rotate when not dragging)
  var autoAngle = 0;
  (function loop() {
    requestAnimationFrame(loop);
    if (!isDragging && mesh) autoAngle += 0.003;
    var a = isDragging ? azimuth : azimuth + autoAngle;
    camera.position.set(
      _camDist * Math.cos(elevation) * Math.cos(a),
      _camDist * Math.cos(elevation) * Math.sin(a),
      _camDist * Math.sin(elevation)
    );
    camera.lookAt(0, 0, 0);
    renderer.render(scene, camera);
  })();
}

// ── STL display ──────────────────────────────────────────────────────────────
function show(buf) {
  try {
    if (mesh) { scene.remove(mesh); mesh = null; }

    var g = parseBinSTL(buf);

    if (!g.attributes.position || g.attributes.position.count === 0) {
      document.getElementById('msg').textContent =
        'Warning: STL parsed but contains no geometry — try recompiling.';
      return;
    }

    // Center geometry at origin; set camera distance from diagonal
    g.computeBoundingBox();
    var center = new THREE.Vector3();
    g.boundingBox.getCenter(center);
    g.translate(-center.x, -center.y, -center.z);
    g.computeBoundingBox();
    var diag = g.boundingBox.getSize(new THREE.Vector3()).length();
    _camDist = diag * 1.8;

    mesh = new THREE.Mesh(g, new THREE.MeshPhongMaterial({
      color: 0xb8c4d0, flatShading: true, side: THREE.DoubleSide
    }));
    scene.add(mesh);
  } catch (e) {
    document.getElementById('msg').textContent = 'STL render error: ' + e.message +
      ' — check browser console for details.';
    console.error('STL render error:', e);
  }
}

function b64buf(b) {
  var s = atob(b), u = new Uint8Array(s.length);
  for (var i = 0; i < s.length; i++) u[i] = s.charCodeAt(i);
  return u.buffer;
}

// ── Check table ──────────────────────────────────────────────────────────────
function renderChecks(checks) {
  var t = document.getElementById('checks'); t.innerHTML = '';
  (checks || []).forEach(function(c) {
    var r = t.insertRow(); r.className = c.passed ? 'p' : 'f';
    r.insertCell().textContent = c.passed ? '✅' : '❌';
    r.insertCell().textContent = (c.node || '') + '.' + (c.claim || '');
    r.insertCell().textContent = c.measured + ' / ' + c.expected;
  });
}

// ── Parameter slider panel ───────────────────────────────────────────────────
// Builds dynamic sliders for every numeric param in the IR so users can tweak
// values without editing raw JSON. Changing a slider updates the JSON textarea
// and auto-recompiles after a short debounce.
var _recompileTimer = null;
function scheduleRecompile() {
  clearTimeout(_recompileTimer);
  _recompileTimer = setTimeout(function() {
    document.getElementById('recompile').click();
  }, 600);
}

function buildParamPanel(ir) {
  var list = document.getElementById('param-list');
  list.innerHTML = '';
  if (!ir || !ir.features) return;

  function addParam(featureId, paramPath, value, irObj, keyPath) {
    if (typeof value !== 'number') return;
    var row = document.createElement('div');
    row.className = 'param-row';

    var label = document.createElement('span');
    label.className = 'param-label';
    label.title = featureId + ' / ' + paramPath;
    label.textContent = featureId + ' / ' + paramPath;
    row.appendChild(label);

    var lo = Math.max(0.1, value * 0.1);
    var hi = value * 4.0;
    var step = value > 10 ? 0.5 : 0.1;

    var slider = document.createElement('input');
    slider.type = 'range'; slider.className = 'param-slider';
    slider.min = lo; slider.max = hi; slider.step = step; slider.value = value;

    var num = document.createElement('input');
    num.type = 'number'; num.className = 'param-num';
    num.min = lo; num.max = hi; num.step = step; num.value = value;

    function applyValue(v) {
      v = parseFloat(v);
      if (isNaN(v)) return;
      // Write back to the IR object via keyPath
      var obj = irObj;
      for (var i = 0; i < keyPath.length - 1; i++) obj = obj[keyPath[i]];
      obj[keyPath[keyPath.length - 1]] = v;
      // Update textarea
      document.getElementById('ir').value = JSON.stringify(ir, null, 2);
      slider.value = v; num.value = v;
      scheduleRecompile();
    }

    slider.oninput = function() { num.value = slider.value; applyValue(slider.value); };
    num.onchange  = function() { slider.value = num.value; applyValue(num.value); };

    row.appendChild(slider);
    row.appendChild(num);
    list.appendChild(row);
  }

  ir.features.forEach(function(feat) {
    var fid = feat.id || '?';
    var params = feat.params || {};
    // Direct params
    Object.keys(params).forEach(function(k) {
      if (typeof params[k] === 'number') {
        addParam(fid, k, params[k], params, [k]);
      }
    });
    // Pattern nested feature params
    if (params.feature && params.feature.params) {
      var nfid = fid + '/' + (params.feature.id || 'item');
      var np = params.feature.params;
      Object.keys(np).forEach(function(k) {
        if (typeof np[k] === 'number') {
          addParam(nfid, k, np[k], np, [k]);
        }
      });
    }
  });

  if (list.children.length > 0) {
    document.getElementById('params').open = true;
  }
}

// ── Load handoff bundle ──────────────────────────────────────────────────────
async function load() {
  init();

  var irRes = await fetch(base + 'ir.json');
  if (!irRes.ok) {
    document.getElementById('msg').textContent =
      'No editable handoff bundle yet — this run did not produce an APPROVED design. ' +
      '(You can still paste an IR below and recompile.)';
    return;
  }
  var irObj = await irRes.json();
  document.getElementById('ir').value = JSON.stringify(irObj, null, 2);
  buildParamPanel(irObj);

  var stlRes = await fetch(base + 'model.stl');
  if (stlRes.ok) {
    show(await stlRes.arrayBuffer());
    document.getElementById('msg').textContent = 'loaded. edit the IR and recompile.';
  } else {
    document.getElementById('msg').textContent = 'IR loaded; no STL preview — edit and recompile.';
  }
}

// ── Recompile ────────────────────────────────────────────────────────────────
document.getElementById('recompile').onclick = async function() {
  var ir;
  try { ir = JSON.parse(document.getElementById('ir').value); }
  catch (e) { alert('Invalid JSON: ' + e); return; }

  document.getElementById('msg').textContent = 'recompiling…';
  var resp = await fetch('/recompile', {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ ir: ir })
  });
  var r = await resp.json();

  var v = document.getElementById('verdict');
  if (r.stl_b64) show(b64buf(r.stl_b64));
  v.textContent  = r.valid ? 'VALID' : ((r.stage || 'L?') + ' FAILED');
  v.className    = 'badge ' + (r.valid ? 'ok' : 'bad');
  renderChecks(r.checks);

  if (r.errors) {
    var t = document.getElementById('checks');
    r.errors.forEach(function(e) {
      var row = t.insertRow(); row.className = 'f';
      row.insertCell().textContent = '❌';
      row.insertCell().colSpan = 2;
      row.cells[1].textContent = (e.node || '') + ': ' + e.detail;
    });
  }
  document.getElementById('msg').textContent = r.valid ? 'Valid — geometry re-rendered.' : 'Validation failed — see check table.';
  // Rebuild sliders from the current (possibly edited) JSON
  try { buildParamPanel(JSON.parse(document.getElementById('ir').value)); } catch(e) {}
};

// ── Reset to original ───────────────────────────────────────────────────────
document.getElementById('reset').onclick = async function() {
  var stlRes = await fetch(base + 'model_original.stl');
  if (!stlRes.ok) {
    document.getElementById('msg').textContent = 'No original saved — this bundle predates baseline preservation.';
    return;
  }
  show(await stlRes.arrayBuffer());
  var irRes = await fetch(base + 'ir_original.json');
  if (irRes.ok) {
    var irObj = await irRes.json();
    document.getElementById('ir').value = JSON.stringify(irObj, null, 2);
    buildParamPanel(irObj);
  }
  document.getElementById('msg').textContent = 'Reset to original approved model.';
  document.getElementById('verdict').textContent = '—';
  document.getElementById('verdict').className = 'badge';
  document.getElementById('checks').innerHTML = '';
};

load();
</script>""".replace("__RID__", run_id)
