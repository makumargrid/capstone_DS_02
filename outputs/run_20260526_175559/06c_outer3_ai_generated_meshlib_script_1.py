
import meshlib.mrmeshpy as mrmesh
import math

check_results = []

# ── helpers ─────────────────────────────────────────────────────────────────
def vec3(x, y, z):
    v = mrmesh.Vector3f()
    v.x = x; v.y = y; v.z = z
    return v

# ── 1. Bounding-box dimensions ───────────────────────────────────────────────
bb = mesh.getBoundingBox()
min_pt = bb.min
max_pt = bb.max

dim_x = max_pt.x - min_pt.x
dim_y = max_pt.y - min_pt.y
dim_z = max_pt.z - min_pt.z

# Expected: ~160.4 x 160.4 x 71.5  (tol ±15)
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

# ── 2. Hub base diameter (Z=0 cross-section at Z≈0) ────────────────────────
# Collect all vertices near Z_min
z_min = min_pt.z
z_max = max_pt.z
z_base_tol = 2.0   # within 2 mm of base

verts_base = []
for v_id in mesh.topology.getValidVerts():
    pt = mesh.points.vec[v_id.get()]
    if pt.z - z_min < z_base_tol:
        verts_base.append(pt)

if verts_base:
    radii_base = [math.sqrt(p.x**2 + p.y**2) for p in verts_base]
    base_diameter = 2 * max(radii_base)
    passed = abs(base_diameter - 100.0) <= 15.0
    check_results.append({
        "check_name": "hub_base_diameter",
        "measured": round(base_diameter, 3),
        "expected": 100.0,
        "passed": passed,
        "unit": "mm",
        "reason": f"Max radius at Z≈{z_min:.2f} = {max(radii_base):.3f} mm → diam {base_diameter:.3f} mm"
    })

# ── 3. Hub top diameter (Z=60 relative to Z_min) ───────────────────────────
z_top_target = z_min + 60.0
z_top_tol = 3.0
verts_top = []
for v_id in mesh.topology.getValidVerts():
    pt = mesh.points.vec[v_id.get()]
    if abs(pt.z - z_top_target) < z_top_tol:
        verts_top.append(pt)

if verts_top:
    radii_top = [math.sqrt(p.x**2 + p.y**2) for p in verts_top]
    top_diameter = 2 * max(radii_top)
    passed = abs(top_diameter - 30.0) <= 15.0
    check_results.append({
        "check_name": "hub_top_diameter",
        "measured": round(top_diameter, 3),
        "expected": 30.0,
        "passed": passed,
        "unit": "mm",
        "reason": f"Max radius at Z≈{z_top_target:.1f} = {max(radii_top):.3f} mm → diam {top_diameter:.3f} mm"
    })

# ── 4. Total hub height ──────────────────────────────────────────────────────
hub_height = dim_z
check_results.append({
    "check_name": "hub_height",
    "measured": round(hub_height, 3),
    "expected": 60.0,
    "passed": abs(hub_height - 60.0) <= 15.0,
    "unit": "mm",
    "reason": f"Z extent = {hub_height:.3f} mm (blades may add height, expected ~60-71.5)"
})

# ── 5. Central bore hole diameter ──────────────────────────────────────────
# Sample vertices very close to the Z axis (r < 20 mm), and look for the
# inner bore ring across all Z levels
bore_verts = []
for v_id in mesh.topology.getValidVerts():
    pt = mesh.points.vec[v_id.get()]
    r = math.sqrt(pt.x**2 + pt.y**2)
    if r < 20.0:
        bore_verts.append((pt, r))

if bore_verts:
    min_bore_r = min(bv[1] for bv in bore_verts)
    max_bore_r = max(bv[1] for bv in bore_verts)
    # The bore inner wall: smallest radii near axis
    # Cluster: r < 10 → inside bore
    inner_bore = [bv[1] for bv in bore_verts if bv[1] < 10.0]
    if inner_bore:
        bore_diameter = 2 * max(inner_bore)
    else:
        bore_diameter = 2 * min_bore_r
    expected_bore = 15.0
    passed = abs(bore_diameter - expected_bore) <= 5.0
    check_results.append({
        "check_name": "central_bore_diameter",
        "measured": round(bore_diameter, 3),
        "expected": expected_bore,
        "passed": passed,
        "unit": "mm",
        "reason": f"Inner bore vertex radius range [{min_bore_r:.3f}, {max_bore_r:.3f}] mm; estimated bore diam {bore_diameter:.3f} mm"
    })
else:
    check_results.append({
        "check_name": "central_bore_diameter",
        "measured": "no vertices near axis",
        "expected": 15.0,
        "passed": False,
        "unit": "mm",
        "reason": "No vertices found within r<20 mm of Z axis; bore may be absent"
    })

# ── 6. Blade count estimation ────────────────────────────────────────────────
# Slice at mid-height Z = z_min + 30, collect vertices in a radial band
# corresponding to blade region (r = 25..65 mm)
z_mid = z_min + 30.0
z_slice_tol = 1.5
blade_band_verts = []
for v_id in mesh.topology.getValidVerts():
    pt = mesh.points.vec[v_id.get()]
    r = math.sqrt(pt.x**2 + pt.y**2)
    if abs(pt.z - z_mid) < z_slice_tol and 20.0 < r < 80.0:
        blade_band_verts.append((math.atan2(pt.y, pt.x), r, pt))

# Sort by angle and look for angular clusters (blade cross-sections)
if blade_band_verts:
    blade_band_verts.sort(key=lambda x: x[0])
    angles = [bv[0] for bv in blade_band_verts]
    # Compute gaps between consecutive angles
    angle_gaps = []
    for i in range(1, len(angles)):
        gap = angles[i] - angles[i-1]
        if gap > 0.3:  # > ~17° gap → new cluster boundary
            angle_gaps.append(gap)
    # Also check wrap-around
    wrap_gap = (angles[0] + 2*math.pi) - angles[-1]
    if wrap_gap > 0.3:
        angle_gaps.append(wrap_gap)
    blade_count_estimate = len(angle_gaps)
    passed = abs(blade_count_estimate - 7) <= 2
    check_results.append({
        "check_name": "blade_count_estimate",
        "measured": blade_count_estimate,
        "expected": 7,
        "passed": passed,
        "unit": "count",
        "reason": f"Angular gap clustering at Z≈{z_mid:.1f} mm found {blade_count_estimate} groups; {len(blade_band_verts)} verts in band"
    })

# ── 7. Blade protrusion height at base ─────────────────────────────────────
# At Z≈z_min (base), the hub cone surface is at r=50.
# Blades protrude outward to r = 50 + 15 = 65 mm.
# Check max radius at base level.
if verts_base:
    max_r_base = max(radii_base)
    expected_max_r = 50.0 + 15.0  # hub radius + protrusion = 65
    passed = abs(max_r_base - expected_max_r) <= 10.0
    check_results.append({
        "check_name": "blade_protrusion_at_base",
        "measured": round(max_r_base, 3),
        "expected": expected_max_r,
        "passed": passed,
        "unit": "mm",
        "reason": f"Max radius at base = {max_r_base:.3f} mm vs expected {expected_max_r:.1f} mm (hub 50 + protrusion 15)"
    })

# ── 8. Blade protrusion height at top ──────────────────────────────────────
if verts_top:
    max_r_top = max(radii_top)
    hub_top_r = 15.0  # top hub radius
    protrusion_top = 5.0
    expected_max_r_top = hub_top_r + protrusion_top  # 20 mm
    passed = abs(max_r_top - expected_max_r_top) <= 8.0
    check_results.append({
        "check_name": "blade_protrusion_at_top",
        "measured": round(max_r_top, 3),
        "expected": expected_max_r_top,
        "passed": passed,
        "unit": "mm",
        "reason": f"Max radius at top = {max_r_top:.3f} mm vs expected {expected_max_r_top:.1f} mm (hub 15 + protrusion 5)"
    })

# ── 9. Min wall thickness (FDM requirement ≥ 2 mm) ─────────────────────────
# Use average edge length as a proxy for mesh resolution, then cast rays
# Sample face normals and cast inward rays
faces = mesh.topology.getValidFaces()
face_list = []
for f_id in faces:
    face_list.append(f_id)

# Sample ~200 faces at random intervals
step = max(1, len(face_list) // 200)
sampled_faces = face_list[::step]

thicknesses = []
for f_id in sampled_faces:
    # Get face center
    tri_pts = mesh.getTriPoints(f_id)
    cx = (tri_pts.a.x + tri_pts.b.x + tri_pts.c.x) / 3.0
    cy = (tri_pts.a.y + tri_pts.b.y + tri_pts.c.y) / 3.0
    cz = (tri_pts.a.z + tri_pts.b.z + tri_pts.c.z) / 3.0
    center = vec3(cx, cy, cz)
    
    # Get face normal (inward = negated)
    n = mesh.normal(f_id)
    inward = vec3(-n.x, -n.y, -n.z)
    
    # Shoot ray inward and find intersection
    origin = vec3(cx + inward.x * 0.01, cy + inward.y * 0.01, cz + inward.z * 0.01)
    result = mesh.findClosestPoint(origin)
    if result:
        hit = result.proj
        dx = hit.x - cx
        dy = hit.y - cy
        dz = hit.z - cz
        dist = math.sqrt(dx*dx + dy*dy + dz*dz)
        if 0.001 < dist < 50.0:
            thicknesses.append(dist)

if thicknesses:
    min_thickness = min(thicknesses)
    avg_thickness = sum(thicknesses) / len(thicknesses)
    passed = min_thickness >= 2.0
    check_results.append({
        "check_name": "min_wall_thickness",
        "measured": round(min_thickness, 3),
        "expected": 2.0,
        "passed": passed,
        "unit": "mm",
        "reason": f"Ray-cast thickness: min={min_thickness:.3f} avg={avg_thickness:.3f} mm over {len(thicknesses)} samples"
    })

# ── 10. Blade twist angle (60 degrees from base to top) ────────────────────
# Find angular position of blade features at base and top, compare shift
# Use outer blade vertices (r > 55 mm) at base and top
outer_base = [(math.atan2(p.x, p.y)) for p in verts_base if math.sqrt(p.x**2+p.y**2) > 52.0]
outer_top  = [(math.atan2(p.x, p.y)) for p in verts_top  if math.sqrt(p.x**2+p.y**2) > 17.0]

if outer_base and outer_top:
    # Histogram: divide 360° into 36 bins of 10° each
    import statistics
    def angle_histogram_peaks(angles_rad, n_bins=36):
        bins = [0]*n_bins
        for a in angles_rad:
            idx = int(((a % (2*math.pi)) / (2*math.pi)) * n_bins) % n_bins
            bins[idx] += 1
        # find top-7 peak bin centers
        sorted_bins = sorted(range(n_bins), key=lambda i: bins[i], reverse=True)
        peak_angles = sorted([(sorted_bins[i] / n_bins * 360.0) for i in range(7)])
        return peak_angles
    
    peaks_base = angle_histogram_peaks(outer_base)
    peaks_top  = angle_histogram_peaks(outer_top)
    # Estimate angular shift by comparing mean of peaks
    mean_base = statistics.mean(peaks_base)
    mean_top  = statistics.mean(peaks_top)
    twist = abs(mean_top - mean_base)
    # Wrap
    if twist > 180: twist = 360 - twist
    passed = abs(twist - 60.0) <= 30.0
    check_results.append({
        "check_name": "blade_twist_angle",
        "measured": round(twist, 2),
        "expected": 60.0,
        "passed": passed,
        "unit": "degrees",
        "reason": f"Peak angle shift base→top ≈ {twist:.2f}° (expected ~60°; ±30° tolerance applied)"
    })

# ── 11. Blade thickness ─────────────────────────────────────────────────────
# Check average edge length in the outer blade region as proxy for mesh quality
# and spot-check blade cross-section width
avg_edge = mesh.averageEdgeLength()
check_results.append({
    "check_name": "avg_edge_length",
    "measured": round(avg_edge, 3),
    "expected": "< 5.0",
    "passed": avg_edge < 5.0,
    "unit": "mm",
    "reason": f"Average mesh edge length = {avg_edge:.3f} mm; fine enough to resolve 2 mm blade thickness"
})

# ── 12. Z axis symmetry (7-fold) ────────────────────────────────────────────
# Count vertices per 360/7 ≈ 51.4° sector. Should be roughly uniform.
sector_count = 7
sector_size = 2*math.pi / sector_count
sector_verts = [0]*sector_count
for v_id in mesh.topology.getValidVerts():
    pt = mesh.points.vec[v_id.get()]
    r = math.sqrt(pt.x**2 + pt.y**2)
    if r > 20.0:  # exclude bore region
        angle = math.atan2(pt.y, pt.x) % (2*math.pi)
        sector_idx = int(angle / sector_size) % sector_count
        sector_verts[sector_idx] += 1

mean_sv = sum(sector_verts) / sector_count
max_sv = max(sector_verts)
min_sv = min(sector_verts)
variation = (max_sv - min_sv) / (mean_sv + 1e-9)
passed = variation < 0.5  # within 50% variation → roughly symmetric
check_results.append({
    "check_name": "7fold_rotational_symmetry",
    "measured": round(variation, 3),
    "expected": "< 0.5",
    "passed": passed,
    "unit": "ratio",
    "reason": f"Sector vertex counts: min={min_sv}, max={max_sv}, mean={mean_sv:.1f}; variation={variation:.3f}"
})

# Print summary for debug
for r in check_results:
    print(f"[{'PASS' if r['passed'] else 'FAIL'}] {r['check_name']}: {r['measured']} {r['unit']} (exp {r['expected']})")
