
import meshlib.mrmeshpy as mrmesh
import math

check_results = []

def vec3(x, y, z):
    v = mrmesh.Vector3f()
    v.x = x; v.y = y; v.z = z
    return v

# ─── BOUNDING BOX ───────────────────────────────────────────────────────────
bb    = mesh.getBoundingBox()
mn    = bb.min;  mx = bb.max
dim_x = mx.x - mn.x
dim_y = mx.y - mn.y
dim_z = mx.z - mn.z
z_min = mn.z;  z_max = mx.z

for cname, measured, expected in [
    ("bbox_x", dim_x, 160.4),
    ("bbox_y", dim_y, 160.4),
    ("bbox_z", dim_z, 71.5),
]:
    tol = 15.0
    passed = abs(measured - expected) <= tol
    check_results.append({
        "check_name": cname,
        "measured":  round(measured, 3),
        "expected":  expected,
        "passed":    passed,
        "unit":      "mm",
        "reason":    f"|{measured:.3f} - {expected}| = {abs(measured-expected):.3f}mm (tol {tol}mm)"
    })

# ─── COLLECT ALL VERTICES ────────────────────────────────────────────────────
all_v = []
for vid in mesh.topology.getValidVerts():
    p = mesh.points.vec[vid.get()]
    all_v.append((p.x, p.y, p.z))
total_verts = len(all_v)

# ─── HUB BASE DIAMETER (Z ≈ z_min, ±2mm) ────────────────────────────────────
z_base_tol = 2.0
vb = [(x, y, z) for x, y, z in all_v if z - z_min < z_base_tol]
radii_base = [math.sqrt(x*x + y*y) for x, y, z in vb]
if radii_base:
    bd = 2.0 * max(radii_base)
    passed = abs(bd - 100.0) <= 15.0
    check_results.append({
        "check_name": "hub_base_outer_diameter",
        "measured":  round(bd, 3),
        "expected":  100.0,
        "passed":    passed,
        "unit":      "mm",
        "reason":    f"Max r at Z∈[{z_min:.2f}, {z_min+z_base_tol:.2f}]mm = {max(radii_base):.3f}mm → Ø{bd:.3f}mm. {len(vb)} verts."
    })

# ─── HUB TOP OUTER DIAMETER (Z ≈ z_min+60, ±3mm) ────────────────────────────
z_top_tgt = z_min + 60.0
vt = [(x, y, z) for x, y, z in all_v if abs(z - z_top_tgt) < 3.0]
radii_top = [math.sqrt(x*x + y*y) for x, y, z in vt]
if radii_top:
    td = 2.0 * max(radii_top)
    passed = abs(td - 30.0) <= 15.0
    check_results.append({
        "check_name": "hub_top_outer_diameter",
        "measured":  round(td, 3),
        "expected":  30.0,
        "passed":    passed,
        "unit":      "mm",
        "reason":    f"Max r at Z≈{z_top_tgt:.1f}mm = {max(radii_top):.3f}mm → Ø{td:.3f}mm. {len(vt)} verts."
    })

# ─── HUB HEIGHT ─────────────────────────────────────────────────────────────
check_results.append({
    "check_name": "hub_total_height",
    "measured":  round(dim_z, 3),
    "expected":  60.0,
    "passed":    abs(dim_z - 60.0) <= 15.0,
    "unit":      "mm",
    "reason":    f"Z extent = {dim_z:.3f}mm. Design spec is 60mm hub body; blades add height → acceptable up to ~75mm."
})

# ─── CENTRAL BORE DIAMETER ──────────────────────────────────────────────────
all_r = sorted([math.sqrt(x*x+y*y) for x, y, z in all_v])
inner  = [r for r in all_r if r < 12.0]
zone20 = [r for r in all_r if r < 20.0]

if inner:
    bd2 = 2.0 * max(inner)
    note = f"{len(inner)} verts inside r<12mm; max r in zone = {max(inner):.3f}mm"
elif zone20:
    bd2 = 2.0 * min(zone20)
    note = f"No verts r<12mm; smallest r in r<20mm zone = {min(zone20):.3f}mm (bore may be solid)"
else:
    bd2 = 2.0 * all_r[0]
    note = f"No verts near axis; min r globally = {all_r[0]:.3f}mm — bore absent"

passed = abs(bd2 - 15.0) <= 5.0
check_results.append({
    "check_name": "central_bore_diameter",
    "measured":  round(bd2, 3),
    "expected":  15.0,
    "passed":    passed,
    "unit":      "mm",
    "reason":    note
})

# ─── BLADE COUNT via ANGULAR GAPS ────────────────────────────────────────────
# Try multiple Z heights and pick best
def count_blades_at_z(z_tgt, z_tol=2.5, r_min=15.0, r_max=90.0, gap_rad=0.30):
    band = sorted([math.atan2(y, x) for x, y, z in all_v
                   if abs(z - z_tgt) < z_tol and r_min < math.sqrt(x*x+y*y) < r_max])
    if len(band) < 5:
        return 0, 0
    gaps = [band[i]-band[i-1] for i in range(1, len(band)) if band[i]-band[i-1] > gap_rad]
    wrap = (band[0] + 2*math.pi) - band[-1]
    if wrap > gap_rad:
        gaps.append(wrap)
    return len(gaps), len(band)

best_count, best_n, best_z = 0, 0, 0
for frac in [0.25, 0.33, 0.50, 0.67, 0.75]:
    z_tst = z_min + frac * 60.0
    c, n = count_blades_at_z(z_tst)
    if n > best_n:
        best_count, best_n, best_z = c, n, z_tst

passed = abs(best_count - 7) <= 2
check_results.append({
    "check_name": "blade_count_estimate",
    "measured":  best_count,
    "expected":  7,
    "passed":    passed,
    "unit":      "count",
    "reason":    f"Best estimate at Z≈{best_z:.1f}mm: {best_count} blades from {best_n} verts (gaps >17.2°). Full scan: z25%={count_blades_at_z(z_min+15)[0]}, z50%={count_blades_at_z(z_min+30)[0]}, z75%={count_blades_at_z(z_min+45)[0]}"
})

# ─── BLADE TIP RADIUS AT BASE ────────────────────────────────────────────────
if radii_base:
    max_rb = max(radii_base)
    expected_rb = 65.0
    passed = abs(max_rb - expected_rb) <= 12.0
    check_results.append({
        "check_name": "blade_tip_radius_at_base",
        "measured":  round(max_rb, 3),
        "expected":  expected_rb,
        "passed":    passed,
        "unit":      "mm",
        "reason":    f"Max r at base = {max_rb:.3f}mm (hub_r=50 + protrusion=15 → expected 65mm). Δ={abs(max_rb-65):.3f}mm"
    })

# ─── BLADE TIP RADIUS AT TOP ─────────────────────────────────────────────────
if radii_top:
    max_rt = max(radii_top)
    expected_rt = 20.0
    passed = abs(max_rt - expected_rt) <= 10.0
    check_results.append({
        "check_name": "blade_tip_radius_at_top",
        "measured":  round(max_rt, 3),
        "expected":  expected_rt,
        "passed":    passed,
        "unit":      "mm",
        "reason":    f"Max r at Z≈{z_top_tgt:.1f}mm = {max_rt:.3f}mm (hub_r=15 + protrusion=5 → expected 20mm). Δ={abs(max_rt-20):.3f}mm"
    })

# ─── WALL THICKNESS via closest-point sampling ───────────────────────────────
face_list = []
for fid in mesh.topology.getValidFaces():
    face_list.append(fid)

step = max(1, len(face_list) // 300)
sampled = face_list[::step]
thick = []

for fid in sampled:
    tri = mesh.getTriPoints(fid)
    p0, p1, p2 = tri[0], tri[1], tri[2]
    cx = (p0.x + p1.x + p2.x) / 3.0
    cy = (p0.y + p1.y + p2.y) / 3.0
    cz = (p0.z + p1.z + p2.z) / 3.0
    n  = mesh.normal(fid)
    probe = vec3(cx - n.x*0.1, cy - n.y*0.1, cz - n.z*0.1)
    res = mesh.findClosestPoint(probe)
    if res and res.valid():
        hp = res.proj.point
        d = math.sqrt((hp.x-cx)**2 + (hp.y-cy)**2 + (hp.z-cz)**2)
        if 0.1 < d < 50.0:
            thick.append(d)

if thick:
    ts = sorted(thick)
    mn_t  = ts[0]
    p5_t  = ts[max(0, int(0.05*len(ts)))]
    avg_t = sum(ts)/len(ts)
    passed = p5_t >= 2.0
    check_results.append({
        "check_name": "wall_thickness_FDM_min_2mm",
        "measured":  round(p5_t, 3),
        "expected":  2.0,
        "passed":    passed,
        "unit":      "mm",
        "reason":    f"5th-pct={p5_t:.3f}mm, min={mn_t:.3f}mm, avg={avg_t:.3f}mm. {len(ts)} samples. FDM requires ≥2mm."
    })

# ─── BLADE TWIST ANGLE ───────────────────────────────────────────────────────
import statistics

ang_base = [math.atan2(y, x) for x, y, z in vb if math.sqrt(x*x+y*y) > 52.0]
ang_top  = [math.atan2(y, x) for x, y, z in vt if math.sqrt(x*x+y*y) > 17.0]

def peak_angles(angles, n_bins=72):
    if not angles:
        return []
    counts = [0]*n_bins
    for a in angles:
        i = int(((a % (2*math.pi)) / (2*math.pi)) * n_bins) % n_bins
        counts[i] += 1
    peaks = []
    for i in range(n_bins):
        if counts[i] > 0 and counts[i] >= counts[(i-1)%n_bins] and counts[i] >= counts[(i+1)%n_bins]:
            peaks.append((i/n_bins*360.0, counts[i]))
    peaks.sort(key=lambda p: -p[1])
    return sorted([p[0] for p in peaks[:7]])

pb = peak_angles(ang_base)
pt = peak_angles(ang_top)

if pb and pt:
    twist = statistics.mean(pt) - statistics.mean(pb)
    if twist >  180: twist -= 360
    if twist < -180: twist += 360
    ta = abs(twist)
    passed = abs(ta - 60.0) <= 35.0
    check_results.append({
        "check_name": "blade_twist_angle_base_to_top",
        "measured":  round(ta, 2),
        "expected":  60.0,
        "passed":    passed,
        "unit":      "degrees",
        "reason":    f"Mean peak shift base→top = {twist:.2f}° (|{ta:.2f}°| vs 60°, ±35° tol). "
                     f"Base peaks: {[round(p,1) for p in pb]}, Top peaks: {[round(p,1) for p in pt]}"
    })

# ─── AVG EDGE LENGTH (mesh resolution) ──────────────────────────────────────
avg_e = mesh.averageEdgeLength()
check_results.append({
    "check_name": "avg_edge_length",
    "measured":  round(avg_e, 3),
    "expected":  "< 5.0",
    "passed":    avg_e < 5.0,
    "unit":      "mm",
    "reason":    f"Avg edge = {avg_e:.3f}mm. {'Fine enough' if avg_e < 5.0 else 'Too coarse'} to resolve 2mm blade thickness."
})

# ─── 7-FOLD ROTATIONAL SYMMETRY ─────────────────────────────────────────────
sec = [0]*7
ssz = 2*math.pi/7
for x, y, z in all_v:
    r = math.sqrt(x*x+y*y)
    if r > 16.0:
        a = math.atan2(y, x) % (2*math.pi)
        sec[int(a/ssz)%7] += 1
msec = sum(sec)/7.0
var  = (max(sec)-min(sec))/(msec+1e-9)
check_results.append({
    "check_name": "7fold_rotational_symmetry",
    "measured":  round(var, 3),
    "expected":  "< 0.5",
    "passed":    var < 0.5,
    "unit":      "ratio",
    "reason":    f"Vertex counts per 51.4° sector: {sec}; (max-min)/mean = {var:.3f}"
})

# ─── FDM OVERHANG ────────────────────────────────────────────────────────────
ov_prob = 0
ov_down = 0
for fid in sampled:
    n = mesh.normal(fid)
    if n.z < 0:
        ov_down += 1
        if n.z > -0.707:   # less steep than 45° → problematic overhang
            ov_prob += 1
total_s = len(sampled)
ov_pct = 100.0 * ov_prob / total_s
check_results.append({
    "check_name": "FDM_overhang_pct",
    "measured":  round(ov_pct, 2),
    "expected":  "< 15.0",
    "passed":    ov_pct < 15.0,
    "unit":      "%",
    "reason":    f"Problematic overhangs (down-facing & <45° from horizontal): {ov_prob}/{total_s} faces = {ov_pct:.1f}%. Down-facing total: {ov_down}/{total_s}."
})

# ─── PRINT SUMMARY ──────────────────────────────────────────────────────────
for r in check_results:
    print(f"[{'PASS' if r['passed'] else 'FAIL'}] {r['check_name']}: {r['measured']} {r['unit']} (exp={r['expected']})")
