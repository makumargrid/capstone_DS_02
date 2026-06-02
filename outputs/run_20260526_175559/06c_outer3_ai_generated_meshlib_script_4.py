
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
z_max = max_pt.z

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

# ─── ALL VERTEX COLLECTION ──────────────────────────────────────────────────
all_verts = []
for v_id in mesh.topology.getValidVerts():
    pt = mesh.points.vec[v_id.get()]
    all_verts.append((pt.x, pt.y, pt.z))

# ─── HUB BASE DIAMETER (Z ≈ z_min, within 2mm) ──────────────────────────────
z_base_tol = 2.0
verts_base = [(x, y, z) for x, y, z in all_verts if z - z_min < z_base_tol]
if verts_base:
    radii_base = [math.sqrt(x**2 + y**2) for x, y, z in verts_base]
    base_diameter = 2.0 * max(radii_base)
    min_r_base = min(radii_base)
    passed = abs(base_diameter - 100.0) <= 15.0
    check_results.append({
        "check_name": "hub_base_outer_diameter",
        "measured": round(base_diameter, 3),
        "expected": 100.0,
        "passed": passed,
        "unit": "mm",
        "reason": f"Max radius at Z≈{z_min:.2f} mm = {max(radii_base):.3f} mm → diam {base_diameter:.3f} mm. {len(verts_base)} verts in slice."
    })

# ─── HUB TOP DIAMETER (Z ≈ z_min + 60) ─────────────────────────────────────
z_top_target = z_min + 60.0
z_top_tol = 3.0
verts_top = [(x, y, z) for x, y, z in all_verts if abs(z - z_top_target) < z_top_tol]
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
        "reason": f"Max radius at Z≈{z_top_target:.1f} mm = {max(radii_top):.3f} mm → diam {top_diameter:.3f} mm. {len(verts_top)} verts."
    })

# ─── HUB HEIGHT ─────────────────────────────────────────────────────────────
check_results.append({
    "check_name": "hub_total_height",
    "measured": round(dim_z, 3),
    "expected": 60.0,
    "passed": abs(dim_z - 60.0) <= 15.0,
    "unit": "mm",
    "reason": f"Z extent = {dim_z:.3f} mm; note blades may protrude above Z=60, expected range 60–75 mm"
})

# ─── CENTRAL BORE DIAMETER ──────────────────────────────────────────────────
# Look for vertices very close to Z axis
bore_all = [(math.sqrt(x**2+y**2), z) for x, y, z in all_verts]
bore_all.sort(key=lambda t: t[0])
# The bore inner wall: find the smallest radii (axis-facing surface)
# Group into r < 15 mm (inside bore)
inner_bore_radii = [r for r, z in bore_all if r < 12.0]
axis_zone_radii  = [r for r, z in bore_all if r < 20.0]

if inner_bore_radii:
    bore_inner_r = max(inner_bore_radii)
    bore_diam = 2.0 * bore_inner_r
    passed = abs(bore_diam - 15.0) <= 5.0
    check_results.append({
        "check_name": "central_bore_diameter",
        "measured": round(bore_diam, 3),
        "expected": 15.0,
        "passed": passed,
        "unit": "mm",
        "reason": f"Largest radius inside r<12mm zone = {bore_inner_r:.3f} mm → bore diam ≈ {bore_diam:.3f} mm. {len(inner_bore_radii)} verts in zone."
    })
elif axis_zone_radii:
    min_r = min(axis_zone_radii)
    bore_diam = 2.0 * min_r
    passed = abs(bore_diam - 15.0) <= 5.0
    check_results.append({
        "check_name": "central_bore_diameter",
        "measured": round(bore_diam, 3),
        "expected": 15.0,
        "passed": passed,
        "unit": "mm",
        "reason": f"Min vertex radius in r<20mm zone = {min_r:.3f} mm → bore diam ≈ {bore_diam:.3f} mm. Note: bore may be solid-filled."
    })
else:
    check_results.append({
        "check_name": "central_bore_diameter",
        "measured": "no vertices near axis",
        "expected": 15.0,
        "passed": False,
        "unit": "mm",
        "reason": "No vertices found within r<20 mm of Z axis — central bore appears absent"
    })

# ─── BLADE COUNT via ANGULAR CLUSTERING at mid-height ───────────────────────
z_mid = z_min + 30.0
z_slice_tol = 2.0
blade_band = []
for x, y, z in all_verts:
    r = math.sqrt(x**2 + y**2)
    if abs(z - z_mid) < z_slice_tol and 20.0 < r < 85.0:
        blade_band.append((math.atan2(y, x), r))

if blade_band:
    blade_band.sort(key=lambda t: t[0])
    angles = [t[0] for t in blade_band]
    
    # Find gaps > 0.25 rad (~14.3°) to identify inter-blade gaps
    gaps = []
    for i in range(1, len(angles)):
        gap = angles[i] - angles[i-1]
        if gap > 0.25:
            gaps.append((angles[i-1], gap))
    wrap = (angles[0] + 2*math.pi) - angles[-1]
    if wrap > 0.25:
        gaps.append((angles[-1], wrap))
    blade_count = len(gaps)
    passed = abs(blade_count - 7) <= 2
    check_results.append({
        "check_name": "blade_count_estimate",
        "measured": blade_count,
        "expected": 7,
        "passed": passed,
        "unit": "count",
        "reason": f"Angular gap analysis at Z≈{z_mid:.1f} mm: {blade_count} gaps (blades) found; {len(blade_band)} verts in slice. Gaps > 14.3° counted."
    })

# ─── BLADE MAX RADIUS AT BASE (protrusion check) ────────────────────────────
# Design: hub base r=50mm, blades protrude 15mm outward → max r = 65mm
if verts_base:
    max_r_base = max(radii_base)
    expected_blade_tip_r = 65.0  # 50+15
    passed = abs(max_r_base - expected_blade_tip_r) <= 12.0
    check_results.append({
        "check_name": "blade_tip_radius_at_base",
        "measured": round(max_r_base, 3),
        "expected": expected_blade_tip_r,
        "passed": passed,
        "unit": "mm",
        "reason": f"Max vertex radius at base Z≈{z_min:.2f}: {max_r_base:.3f} mm vs expected 65 mm (hub 50 + protrusion 15)"
    })

# ─── BLADE MAX RADIUS AT TOP (protrusion check) ──────────────────────────────
# Design: hub top r=15mm, blades protrude 5mm → max r = 20mm
if verts_top:
    max_r_top = max(radii_top)
    expected_top_tip_r = 20.0  # 15+5
    passed = abs(max_r_top - expected_top_tip_r) <= 10.0
    check_results.append({
        "check_name": "blade_tip_radius_at_top",
        "measured": round(max_r_top, 3),
        "expected": expected_top_tip_r,
        "passed": passed,
        "unit": "mm",
        "reason": f"Max vertex radius at Z≈{z_top_target:.1f}: {max_r_top:.3f} mm vs expected 20 mm (hub 15 + protrusion 5)"
    })

# ─── WALL THICKNESS via closest-point probing ───────────────────────────────
face_list = []
for f_id in mesh.topology.getValidFaces():
    face_list.append(f_id)

step = max(1, len(face_list) // 300)
sampled_faces = face_list[::step]
thicknesses = []

for f_id in sampled_faces:
    tri_pts = mesh.getTriPoints(f_id)   # std_array[0],[1],[2]
    p0 = tri_pts[0]; p1 = tri_pts[1]; p2 = tri_pts[2]
    cx = (p0.x + p1.x + p2.x) / 3.0
    cy = (p0.y + p1.y + p2.y) / 3.0
    cz = (p0.z + p1.z + p2.z) / 3.0
    
    n = mesh.normal(f_id)
    # offset slightly inward
    probe_pt = vec3(cx - n.x * 0.05, cy - n.y * 0.05, cz - n.z * 0.05)
    
    result = mesh.findClosestPoint(probe_pt)
    if result:
        hit = result.proj
        dx = hit.x - cx
        dy = hit.y - cy
        dz = hit.z - cz
        dist = math.sqrt(dx*dx + dy*dy + dz*dz)
        if 0.05 < dist < 40.0:
            thicknesses.append(dist)

if thicknesses:
    min_t = min(thicknesses)
    avg_t = sum(thicknesses) / len(thicknesses)
    pct5  = sorted(thicknesses)[int(0.05 * len(thicknesses))]
    passed = pct5 >= 2.0
    check_results.append({
        "check_name": "wall_thickness_FDM_min_2mm",
        "measured": round(pct5, 3),
        "expected": 2.0,
        "passed": passed,
        "unit": "mm",
        "reason": f"5th-pct thickness={pct5:.3f} min={min_t:.3f} avg={avg_t:.3f} mm over {len(thicknesses)} samples (FDM requires ≥2mm)"
    })

# ─── BLADE TWIST ANGLE ───────────────────────────────────────────────────────
# Compare angular distribution of blade-tip verts at base vs top
outer_base_angles = [math.atan2(y, x) for x, y, z in verts_base if math.sqrt(x**2+y**2) > 52.0]
outer_top_angles  = [math.atan2(y, x) for x, y, z in verts_top  if math.sqrt(x**2+y**2) > 17.0]

if outer_base_angles and outer_top_angles:
    import statistics
    def histogram_peaks(angles_rad, n_bins=72):
        bins = [[] for _ in range(n_bins)]
        for a in angles_rad:
            idx = int(((a % (2*math.pi)) / (2*math.pi)) * n_bins) % n_bins
            bins[idx].append(a)
        counts = [len(b) for b in bins]
        # find local maxima
        peaks = []
        for i in range(n_bins):
            if counts[i] > 0 and counts[i] >= counts[(i-1) % n_bins] and counts[i] >= counts[(i+1) % n_bins]:
                peak_angle_deg = (i / n_bins) * 360.0
                peaks.append((peak_angle_deg, counts[i]))
        peaks.sort(key=lambda p: -p[1])
        top_peaks = sorted([p[0] for p in peaks[:7]])
        return top_peaks

    peaks_base = histogram_peaks(outer_base_angles)
    peaks_top  = histogram_peaks(outer_top_angles)
    
    if peaks_base and peaks_top:
        mean_base = statistics.mean(peaks_base)
        mean_top  = statistics.mean(peaks_top)
        twist = mean_top - mean_base
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
            "reason": f"Histogram peak shift base→top ≈ {twist:.2f}° (|{twist_abs:.2f}°| vs expected 60°; ±35° tol). "
                      f"Base peaks: {[round(p,1) for p in peaks_base]}, Top peaks: {[round(p,1) for p in peaks_top]}"
        })

# ─── AVERAGE EDGE LENGTH (mesh resolution check) ────────────────────────────
avg_edge = mesh.averageEdgeLength()
check_results.append({
    "check_name": "avg_edge_length_mesh_resolution",
    "measured": round(avg_edge, 3),
    "expected": "< 5.0",
    "passed": avg_edge < 5.0,
    "unit": "mm",
    "reason": f"Avg edge = {avg_edge:.3f} mm; {'fine' if avg_edge < 5 else 'coarse'} enough to resolve 2mm blade thickness"
})

# ─── 7-FOLD ROTATIONAL SYMMETRY ─────────────────────────────────────────────
sector_count = 7
sector_size = 2 * math.pi / sector_count
sector_verts = [0] * sector_count
for x, y, z in all_verts:
    r = math.sqrt(x**2 + y**2)
    if r > 20.0:
        angle = math.atan2(y, x) % (2 * math.pi)
        idx = int(angle / sector_size) % sector_count
        sector_verts[idx] += 1

mean_sv = sum(sector_verts) / sector_count
max_sv = max(sector_verts)
min_sv = min(sector_verts)
variation = (max_sv - min_sv) / (mean_sv + 1e-9)
check_results.append({
    "check_name": "7fold_rotational_symmetry",
    "measured": round(variation, 3),
    "expected": "< 0.5",
    "passed": variation < 0.5,
    "unit": "ratio",
    "reason": f"Vertex counts per 51.4° sector: {sector_verts}; variation (max-min)/mean = {variation:.3f}"
})

# ─── FDM OVERHANG ANGLE CHECK ────────────────────────────────────────────────
# Overhang angle from vertical; FDM limit ~45° from horizontal (i.e., face normal Z component < 0 AND angle > 45° from vertical)
overhang_limit_deg = 45.0
overhang_cos = math.cos(math.radians(90.0 - overhang_limit_deg))  # = cos(45°)

overhang_faces = 0
total_faces_checked = 0
for f_id in sampled_faces:
    n = mesh.normal(f_id)
    # downward-facing (nz < 0) with |nz| < cos(45°) = overhanging
    if n.z < 0:
        total_faces_checked += 1
        angle_from_horiz = math.degrees(math.asin(abs(n.z)))  # angle below horizontal
        if angle_from_horiz < overhang_limit_deg:
            overhang_faces += 1

overhang_pct = 100.0 * overhang_faces / (len(sampled_faces) + 1e-9)
passed = overhang_pct < 15.0  # <15% of faces are severe overhangs
check_results.append({
    "check_name": "FDM_overhang_angle_severity",
    "measured": round(overhang_pct, 2),
    "expected": "< 15%",
    "passed": passed,
    "unit": "%",
    "reason": f"{overhang_faces}/{len(sampled_faces)} sampled faces are downward-facing overhangs >45° from vertical ({overhang_pct:.1f}%)"
})

# ─── PRINT SUMMARY ──────────────────────────────────────────────────────────
for r in check_results:
    print(f"[{'PASS' if r['passed'] else 'FAIL'}] {r['check_name']}: {r['measured']} {r['unit']} (exp {r['expected']})")
