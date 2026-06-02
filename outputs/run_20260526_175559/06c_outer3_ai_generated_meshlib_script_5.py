
import meshlib.mrmeshpy as mrmesh
import math

check_results = []

def vec3(x, y, z):
    v = mrmesh.Vector3f()
    v.x = x; v.y = y; v.z = z
    return v

# ─── BOUNDING BOX ───────────────────────────────────────────────────────────
bb = mesh.getBoundingBox()
min_pt = bb.min
max_pt = bb.max
dim_x = max_pt.x - min_pt.x
dim_y = max_pt.y - min_pt.y
dim_z = max_pt.z - min_pt.z
z_min = min_pt.z

for name, measured, expected in [
    ("bbox_x", dim_x, 160.4),
    ("bbox_y", dim_y, 160.4),
    ("bbox_z", dim_z, 71.5),
]:
    tol = 15.0
    passed = abs(measured - expected) <= tol
    check_results.append({
        "check_name": name,
        "measured": round(measured, 3),
        "expected": expected,
        "passed": passed,
        "unit": "mm",
        "reason": f"|{measured:.3f} - {expected}| = {abs(measured-expected):.3f} vs tol {tol}"
    })

# ─── COLLECT ALL VERTICES ────────────────────────────────────────────────────
all_verts = []
for v_id in mesh.topology.getValidVerts():
    pt = mesh.points.vec[v_id.get()]
    all_verts.append((pt.x, pt.y, pt.z))

# ─── HUB BASE DIAMETER (Z ≈ z_min) ──────────────────────────────────────────
z_base_tol = 2.0
verts_base = [(x, y, z) for x, y, z in all_verts if z - z_min < z_base_tol]
radii_base = []
if verts_base:
    radii_base = [math.sqrt(x**2 + y**2) for x, y, z in verts_base]
    base_diameter = 2.0 * max(radii_base)
    passed = abs(base_diameter - 100.0) <= 15.0
    check_results.append({
        "check_name": "hub_base_outer_diameter",
        "measured": round(base_diameter, 3),
        "expected": 100.0,
        "passed": passed,
        "unit": "mm",
        "reason": f"Max vertex radius at Z≈{z_min:.2f}mm = {max(radii_base):.3f}mm → diam {base_diameter:.3f}mm ({len(verts_base)} verts in ±{z_base_tol}mm slice)"
    })

# ─── HUB TOP DIAMETER (Z ≈ z_min + 60) ─────────────────────────────────────
z_top_target = z_min + 60.0
z_top_tol = 3.0
verts_top = [(x, y, z) for x, y, z in all_verts if abs(z - z_top_target) < z_top_tol]
radii_top = []
if verts_top:
    radii_top = [math.sqrt(x**2 + y**2) for x, y, z in verts_top]
    top_diameter = 2.0 * max(radii_top)
    passed = abs(top_diameter - 30.0) <= 15.0
    check_results.append({
        "check_name": "hub_top_outer_diameter",
        "measured": round(top_diameter, 3),
        "expected": 30.0,
        "passed": passed,
        "unit": "mm",
        "reason": f"Max vertex radius at Z≈{z_top_target:.1f}mm = {max(radii_top):.3f}mm → diam {top_diameter:.3f}mm ({len(verts_top)} verts)"
    })

# ─── TOTAL HEIGHT ────────────────────────────────────────────────────────────
check_results.append({
    "check_name": "hub_total_height",
    "measured": round(dim_z, 3),
    "expected": 60.0,
    "passed": abs(dim_z - 60.0) <= 15.0,
    "unit": "mm",
    "reason": f"Z extent = {dim_z:.3f}mm; blades may add height above Z=60mm, acceptable range ~60–75mm"
})

# ─── CENTRAL BORE DIAMETER ──────────────────────────────────────────────────
bore_radii = sorted([math.sqrt(x**2 + y**2) for x, y, z in all_verts])
inner_bore = [r for r in bore_radii if r < 12.0]
axis_zone  = [r for r in bore_radii if r < 20.0]
min_bore_r = bore_radii[0] if bore_radii else None

if inner_bore:
    bore_diam = 2.0 * max(inner_bore)
    note = f"Bore inner wall vertices in r<12mm: {len(inner_bore)} verts, max_r={max(inner_bore):.3f}mm"
elif axis_zone:
    bore_diam = 2.0 * min(axis_zone)
    note = f"No verts r<12mm; min vertex radius={min(axis_zone):.3f}mm (bore may be solid-filled)"
else:
    bore_diam = 2.0 * min_bore_r if min_bore_r else -1
    note = f"Min vertex radius across all verts = {min_bore_r:.3f}mm — bore likely absent"

passed = abs(bore_diam - 15.0) <= 5.0
check_results.append({
    "check_name": "central_bore_diameter",
    "measured": round(bore_diam, 3),
    "expected": 15.0,
    "passed": passed,
    "unit": "mm",
    "reason": note
})

# ─── BLADE COUNT via ANGULAR GAPS at mid-height ─────────────────────────────
z_mid = z_min + 30.0
z_slice_tol = 2.5
blade_band = []
for x, y, z in all_verts:
    r = math.sqrt(x**2 + y**2)
    if abs(z - z_mid) < z_slice_tol and 18.0 < r < 90.0:
        blade_band.append(math.atan2(y, x))

if blade_band:
    blade_band_s = sorted(blade_band)
    gaps = []
    for i in range(1, len(blade_band_s)):
        g = blade_band_s[i] - blade_band_s[i-1]
        if g > 0.3:
            gaps.append(g)
    wrap = (blade_band_s[0] + 2*math.pi) - blade_band_s[-1]
    if wrap > 0.3:
        gaps.append(wrap)
    blade_count = len(gaps)
    passed = abs(blade_count - 7) <= 2
    check_results.append({
        "check_name": "blade_count_estimate",
        "measured": blade_count,
        "expected": 7,
        "passed": passed,
        "unit": "count",
        "reason": f"Angular gaps >0.3rad at Z≈{z_mid:.1f}mm in r∈[18,90]: {blade_count} gaps detected from {len(blade_band)} verts. Gap sizes: {sorted([round(g*180/math.pi,1) for g in sorted(gaps, reverse=True)[:10]])}°"
    })
else:
    check_results.append({
        "check_name": "blade_count_estimate",
        "measured": 0,
        "expected": 7,
        "passed": False,
        "unit": "count",
        "reason": f"No vertices found in blade band at Z≈{z_mid:.1f}mm"
    })

# ─── BLADE PROTRUSION AT BASE ────────────────────────────────────────────────
if radii_base:
    max_r_base = max(radii_base)
    expected_r = 65.0  # 50 + 15
    passed = abs(max_r_base - expected_r) <= 12.0
    check_results.append({
        "check_name": "blade_tip_radius_at_base",
        "measured": round(max_r_base, 3),
        "expected": expected_r,
        "passed": passed,
        "unit": "mm",
        "reason": f"Max radius at base = {max_r_base:.3f}mm; expected 65mm (hub 50mm + protrusion 15mm). Delta = {abs(max_r_base-expected_r):.3f}mm"
    })

# ─── BLADE PROTRUSION AT TOP ─────────────────────────────────────────────────
if radii_top:
    max_r_top = max(radii_top)
    expected_r_top = 20.0  # 15 + 5
    passed = abs(max_r_top - expected_r_top) <= 10.0
    check_results.append({
        "check_name": "blade_tip_radius_at_top",
        "measured": round(max_r_top, 3),
        "expected": expected_r_top,
        "passed": passed,
        "unit": "mm",
        "reason": f"Max radius at top Z={z_top_target:.1f}mm = {max_r_top:.3f}mm; expected 20mm (hub 15mm + protrusion 5mm). Delta = {abs(max_r_top-expected_r_top):.3f}mm"
    })

# ─── WALL THICKNESS (FDM min 2mm) via closest-point ─────────────────────────
face_list = []
for f_id in mesh.topology.getValidFaces():
    face_list.append(f_id)

step = max(1, len(face_list) // 250)
sampled_faces = face_list[::step]
thicknesses = []

for f_id in sampled_faces:
    tri_pts = mesh.getTriPoints(f_id)
    p0 = tri_pts[0]; p1 = tri_pts[1]; p2 = tri_pts[2]
    cx = (p0.x + p1.x + p2.x) / 3.0
    cy = (p0.y + p1.y + p2.y) / 3.0
    cz = (p0.z + p1.z + p2.z) / 3.0

    n = mesh.normal(f_id)
    # probe inward from face center
    probe_pt = vec3(cx - n.x * 0.1, cy - n.y * 0.1, cz - n.z * 0.1)
    result = mesh.findClosestPoint(probe_pt)
    if result and result.valid():
        hit_pt = result.proj.point
        dx = hit_pt.x - cx
        dy = hit_pt.y - cy
        dz = hit_pt.z - cz
        dist = math.sqrt(dx*dx + dy*dy + dz*dz)
        if 0.1 < dist < 50.0:
            thicknesses.append(dist)

if thicknesses:
    ts = sorted(thicknesses)
    min_t  = ts[0]
    pct5_t = ts[max(0, int(0.05*len(ts)))]
    avg_t  = sum(ts)/len(ts)
    passed = pct5_t >= 2.0
    check_results.append({
        "check_name": "wall_thickness_FDM_min_2mm",
        "measured": round(pct5_t, 3),
        "expected": 2.0,
        "passed": passed,
        "unit": "mm",
        "reason": f"5th-pct={pct5_t:.3f}mm, min={min_t:.3f}mm, avg={avg_t:.3f}mm over {len(ts)} samples. FDM requires ≥2mm."
    })

# ─── BLADE TWIST ANGLE ───────────────────────────────────────────────────────
outer_base = [math.atan2(y, x) for x, y, z in verts_base if math.sqrt(x**2+y**2) > 52.0]
outer_top  = [math.atan2(y, x) for x, y, z in verts_top  if math.sqrt(x**2+y**2) > 17.0]

if outer_base and outer_top:
    import statistics
    def histo_peaks(angles, n_bins=72):
        counts = [0]*n_bins
        for a in angles:
            idx = int(((a % (2*math.pi)) / (2*math.pi)) * n_bins) % n_bins
            counts[idx] += 1
        peaks = []
        for i in range(n_bins):
            prev_i = (i-1) % n_bins
            next_i = (i+1) % n_bins
            if counts[i] > 0 and counts[i] >= counts[prev_i] and counts[i] >= counts[next_i]:
                peaks.append((i / n_bins * 360.0, counts[i]))
        peaks.sort(key=lambda p: -p[1])
        return sorted([p[0] for p in peaks[:7]])

    pb = histo_peaks(outer_base)
    pt = histo_peaks(outer_top)
    if pb and pt:
        twist = statistics.mean(pt) - statistics.mean(pb)
        if twist > 180: twist -= 360
        if twist < -180: twist += 360
        twist_abs = abs(twist)
        passed = abs(twist_abs - 60.0) <= 35.0
        check_results.append({
            "check_name": "blade_twist_angle",
            "measured": round(twist_abs, 2),
            "expected": 60.0,
            "passed": passed,
            "unit": "degrees",
            "reason": f"Peak angle shift base→top ≈ {twist:.2f}° (|{twist_abs:.2f}°| vs expected 60°, ±35° tol). "
                      f"Base peaks: {[round(p,1) for p in pb]}, Top peaks: {[round(p,1) for p in pt]}"
        })

# ─── AVERAGE EDGE LENGTH ──────────────────────────────────────────────────────
avg_edge = mesh.averageEdgeLength()
check_results.append({
    "check_name": "avg_edge_length_mesh_resolution",
    "measured": round(avg_edge, 3),
    "expected": "< 5.0",
    "passed": avg_edge < 5.0,
    "unit": "mm",
    "reason": f"Avg edge = {avg_edge:.3f}mm; {'sufficient' if avg_edge < 5 else 'too coarse'} to resolve 2mm features"
})

# ─── 7-FOLD SYMMETRY ─────────────────────────────────────────────────────────
n_sectors = 7
sec_size  = 2*math.pi / n_sectors
sec_counts = [0]*n_sectors
for x, y, z in all_verts:
    r = math.sqrt(x**2+y**2)
    if r > 18.0:
        a = math.atan2(y, x) % (2*math.pi)
        sec_counts[int(a / sec_size) % n_sectors] += 1
mean_sc = sum(sec_counts) / n_sectors
variation = (max(sec_counts) - min(sec_counts)) / (mean_sc + 1e-9)
check_results.append({
    "check_name": "7fold_rotational_symmetry",
    "measured": round(variation, 3),
    "expected": "< 0.5",
    "passed": variation < 0.5,
    "unit": "ratio",
    "reason": f"Sector vertex distribution (7 sectors of 51.4°): {sec_counts}; (max-min)/mean = {variation:.3f}"
})

# ─── FDM OVERHANG CHECK ──────────────────────────────────────────────────────
overhang_count = 0
downward_count = 0
for f_id in sampled_faces:
    n = mesh.normal(f_id)
    if n.z < 0:
        downward_count += 1
        # angle between face normal and -Z: acos(-nz). Overhang > 45° from vertical → nz > -0.707
        if n.z > -0.707:   # less than 45° below horizontal
            overhang_count += 1
total = len(sampled_faces)
overhang_pct = 100.0 * overhang_count / total
check_results.append({
    "check_name": "FDM_overhang_faces_pct",
    "measured": round(overhang_pct, 2),
    "expected": "< 15%",
    "passed": overhang_pct < 15.0,
    "unit": "%",
    "reason": f"{overhang_count}/{total} sampled faces are problematic overhangs (down-facing, <45° from horizontal). "
              f"Total downward-facing: {downward_count}/{total}."
})

# ─── PRINT SUMMARY ──────────────────────────────────────────────────────────
for r in check_results:
    print(f"[{'PASS' if r['passed'] else 'FAIL'}] {r['check_name']}: measured={r['measured']} {r['unit']}, expected={r['expected']}")
