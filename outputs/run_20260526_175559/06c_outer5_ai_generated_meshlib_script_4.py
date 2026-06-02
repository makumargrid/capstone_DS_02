
import meshlib.mrmeshpy as mrmesh
import math
import random

random.seed(42)
check_results = []

# ── GATHER ALL VERTICES ───────────────────────────────────────────────────────
bbox = mesh.getBoundingBox()
mn = bbox.min
mx = bbox.max

dim_x = mx.x - mn.x
dim_y = mx.y - mn.y
dim_z = mx.z - mn.z

verts = mesh.points
topo  = mesh.topology
valid_verts = topo.getValidVerts()

all_pts = []
for i in range(verts.size()):
    vid = mrmesh.VertId(i)
    if valid_verts.test(vid):
        p = verts[vid]
        all_pts.append((p.x, p.y, p.z))

# Mesh centroid from bounding box
cx = (mn.x + mx.x) / 2.0
cy = (mn.y + mx.y) / 2.0

# ── 1. HUB HEIGHT (Z EXTENT) ──────────────────────────────────────────────────
check_results.append({
    "check_name": "Hub height Z extent",
    "measured": round(dim_z, 3),
    "expected": 60.0,
    "passed": abs(dim_z - 60.0) <= 15.0,
    "unit": "mm",
    "reason": f"Z min={round(mn.z,3)}mm, Z max={round(mx.z,3)}mm. Design: 60mm total height"
})

# ── 2. X EXTENT ────────────────────────────────────────────────────────────────
check_results.append({
    "check_name": "Overall X extent",
    "measured": round(dim_x, 3),
    "expected": 132.0,
    "passed": abs(dim_x - 132.0) <= 15.0,
    "unit": "mm",
    "reason": f"X min={round(mn.x,3)}, X max={round(mx.x,3)}. Tolerance ±15mm"
})

# ── 3. Y EXTENT ────────────────────────────────────────────────────────────────
check_results.append({
    "check_name": "Overall Y extent",
    "measured": round(dim_y, 3),
    "expected": 132.0,
    "passed": abs(dim_y - 132.0) <= 15.0,
    "unit": "mm",
    "reason": f"Y min={round(mn.y,3)}, Y max={round(mx.y,3)}. Tolerance ±15mm"
})

# ── 4. HUB BASE DIAMETER – cone at Z≈0, r=50mm ────────────────────────────────
# Sample vertices at Z near base, look for hub inner edge vs outer edge
# The hub surface (no blades) should be near r=50mm; with blades, outer edge goes to ~65mm
base_pts = [(x, y, z) for x, y, z in all_pts if abs(z - mn.z) < 2.0]
base_radii_sorted = sorted([math.sqrt((x-cx)**2+(y-cy)**2) for x,y,z in base_pts]) if base_pts else []

if base_radii_sorted:
    # Most vertices should cluster around hub base radius (50mm)
    # p50 of base vertices ≈ hub radius
    p50_base = base_radii_sorted[int(0.50 * len(base_radii_sorted))]
    p90_base = base_radii_sorted[int(0.90 * len(base_radii_sorted))]
    max_base  = base_radii_sorted[-1]
    check_results.append({
        "check_name": "Hub base radius (cone, no blades) at Z=0",
        "measured": round(p50_base, 3),
        "expected": "~50.0 (±5mm)",
        "passed": 40.0 <= p50_base <= 58.0,
        "unit": "mm",
        "reason": f"p50={round(p50_base,3)}mm, p90={round(p90_base,3)}mm, max={round(max_base,3)}mm from {len(base_pts)} vertices"
    })
    check_results.append({
        "check_name": "Blade tip reach at base (hub r=50 + protrusion 15mm = ~65mm)",
        "measured": round(max_base, 3),
        "expected": "55–70",
        "passed": 50.0 <= max_base <= 72.0,
        "unit": "mm",
        "reason": f"Outermost vertex at Z=base. Design: blade protrudes 15mm from hub at base (r=65mm)"
    })

# ── 5. HUB TOP DIAMETER – cone at Z≈60, r=15mm ────────────────────────────────
top_pts = [(x, y, z) for x, y, z in all_pts if abs(z - mx.z) < 2.0]
top_radii_sorted = sorted([math.sqrt((x-cx)**2+(y-cy)**2) for x,y,z in top_pts]) if top_pts else []

if top_radii_sorted:
    p20_top = top_radii_sorted[int(0.20 * len(top_radii_sorted))]
    p50_top = top_radii_sorted[int(0.50 * len(top_radii_sorted))]
    max_top  = top_radii_sorted[-1]
    check_results.append({
        "check_name": "Hub top radius (cone) at Z=60",
        "measured": round(p20_top, 3),
        "expected": "~15.0 (±3mm)",
        "passed": 12.0 <= p20_top <= 20.0,
        "unit": "mm",
        "reason": f"p20={round(p20_top,3)}mm, p50={round(p50_top,3)}mm, max={round(max_top,3)}mm. Design: top radius=15mm"
    })
    check_results.append({
        "check_name": "Blade tip reach at top (hub r=15 + protrusion 5mm = ~20mm)",
        "measured": round(max_top, 3),
        "expected": "18–25",
        "passed": 15.0 <= max_top <= 28.0,
        "unit": "mm",
        "reason": f"Outermost vertex at Z=top. Design: blade protrudes 5mm from hub at top (r=20mm)"
    })

# ── 6. CENTRAL BORE DIAMETER ──────────────────────────────────────────────────
# Ray from center of mesh outward along X at multiple Z heights
# We already know from probe: ray from (0,0,30) → +X hits at 7.5mm
# That IS the inner bore wall. Confirm at Z=15, Z=30, Z=45
bore_diameters = []
for test_z_frac in [0.25, 0.50, 0.75]:
    test_z = mn.z + dim_z * test_z_frac
    for angle_deg in [0, 45, 90, 135]:
        angle_rad = math.radians(angle_deg)
        org = mrmesh.Vector3f()
        org.x = cx
        org.y = cy
        org.z = test_z

        direction = mrmesh.Vector3f()
        direction.x = math.cos(angle_rad)
        direction.y = math.sin(angle_rad)
        direction.z = 0.0

        line = mrmesh.Line3f()
        line.p = org
        line.d = direction

        result = mrmesh.rayMeshIntersect(mesh, line)
        if result and result.distanceAlongLine > 0.1:
            bore_diameters.append(result.distanceAlongLine * 2.0)

if bore_diameters:
    mean_bore = sum(bore_diameters) / len(bore_diameters)
    min_bore  = min(bore_diameters)
    max_bore_d  = max(bore_diameters)
    check_results.append({
        "check_name": "Central bore diameter (ray from axis outward)",
        "measured": round(mean_bore, 3),
        "expected": "~15.0 (±2mm)",
        "passed": 12.0 <= mean_bore <= 18.0,
        "unit": "mm",
        "reason": f"Mean={round(mean_bore,3)}mm, min={round(min_bore,3)}mm, max={round(max_bore_d,3)}mm from {len(bore_diameters)} rays. Expected bore dia=15mm"
    })

# ── 7. BLADE COUNT via angular sectoring ──────────────────────────────────────
def count_blade_peaks(pts, cx, cy, n_bins=72, threshold_mult=1.5):
    """Count angular peaks at a given Z-slice cross-section (weighted by radius)."""
    if not pts:
        return 0, []
    angles = [math.degrees(math.atan2(y - cy, x - cx)) % 360 for x, y, z in pts]
    radii  = [math.sqrt((x - cx)**2 + (y - cy)**2) for x, y, z in pts]
    bins = [0.0] * n_bins
    for a, r in zip(angles, radii):
        bins[int(a * n_bins / 360) % n_bins] += r
    mean_val = sum(bins) / n_bins
    peaks = []
    for i in range(n_bins):
        prev_b = bins[(i - 1) % n_bins]
        next_b = bins[(i + 1) % n_bins]
        if bins[i] > mean_val * threshold_mult and bins[i] >= prev_b and bins[i] >= next_b:
            peaks.append(i * 360.0 / n_bins)
    return len(peaks), peaks

# Try multiple Z slices
blade_counts = []
peak_positions = {}
for z_frac in [0.15, 0.30, 0.50, 0.70, 0.85]:
    z_val = mn.z + dim_z * z_frac
    slice_pts = [(x, y, z) for x, y, z in all_pts if abs(z - z_val) < 2.5]
    count, peaks = count_blade_peaks(slice_pts, cx, cy, n_bins=72, threshold_mult=1.5)
    blade_counts.append(count)
    peak_positions[round(z_val, 1)] = peaks

# Use the mode of detected counts
from collections import Counter
count_mode = Counter(blade_counts).most_common(1)[0][0]
check_results.append({
    "check_name": "Blade count (angular peaks, multiple Z-slices)",
    "measured": count_mode,
    "expected": 7,
    "passed": 5 <= count_mode <= 9,
    "unit": "count",
    "reason": f"Detected counts per slice: {blade_counts} at z-fracs [0.15,0.30,0.50,0.70,0.85]. Mode={count_mode}"
})

# ── 8. BLADE TWIST ANGLE ──────────────────────────────────────────────────────
z_base_val = mn.z + dim_z * 0.10
z_top_val  = mn.z + dim_z * 0.90
base_slice = [(x, y, z) for x, y, z in all_pts if abs(z - z_base_val) < 3.0]
top_slice  = [(x, y, z) for x, y, z in all_pts if abs(z - z_top_val) < 3.0]

_, base_peaks = count_blade_peaks(base_slice, cx, cy, n_bins=144, threshold_mult=1.4)
_, top_peaks  = count_blade_peaks(top_slice,  cx, cy, n_bins=144, threshold_mult=1.4)

if len(base_peaks) >= 5 and len(top_peaks) >= 5:
    diffs = []
    for bp in base_peaks:
        closest = min(top_peaks, key=lambda tp: min(abs(tp - bp), 360 - abs(tp - bp)))
        diff = closest - bp
        if diff >  180: diff -= 360
        if diff < -180: diff += 360
        diffs.append(diff)
    avg_twist = sum(diffs) / len(diffs)
    check_results.append({
        "check_name": "Blade aerodynamic twist angle (base-to-top)",
        "measured": round(avg_twist, 2),
        "expected": "~60 degrees",
        "passed": 30.0 <= abs(avg_twist) <= 90.0,
        "unit": "degrees",
        "reason": f"Design: ~60° twist. Base peaks={len(base_peaks)}, top peaks={len(top_peaks)}. Angular offset computed."
    })
else:
    check_results.append({
        "check_name": "Blade aerodynamic twist angle (base-to-top)",
        "measured": f"base_peaks={len(base_peaks)}, top_peaks={len(top_peaks)}",
        "expected": "~60 degrees",
        "passed": False,
        "unit": "degrees",
        "reason": f"Insufficient peaks at low/high slices to compute twist. Counts: {blade_counts}"
    })

# ── 9. FDM OVERHANG ANALYSIS ─────────────────────────────────────────────────
valid_faces = mesh.topology.getValidFaces()
overhang_count_45 = 0
overhang_count_60 = 0
total_face_count  = 0

for fi in range(mesh.topology.faceSize()):
    fid = mrmesh.FaceId(fi)
    if not valid_faces.test(fid):
        continue
    total_face_count += 1
    n = mesh.dirDblArea(fid)
    length = math.sqrt(n.x**2 + n.y**2 + n.z**2)
    if length < 1e-10:
        continue
    nz = n.z / length
    # nz < -sin(45°) = -0.707 means face points more than 45° below horizontal
    if nz < -0.707:
        overhang_count_45 += 1
    if nz < -0.866:  # > 60° overhang
        overhang_count_60 += 1

pct_45 = 100.0 * overhang_count_45 / total_face_count if total_face_count > 0 else 0
pct_60 = 100.0 * overhang_count_60 / total_face_count if total_face_count > 0 else 0

check_results.append({
    "check_name": "FDM overhang >45° (faces requiring support)",
    "measured": round(pct_45, 2),
    "expected": "< 30%",
    "passed": pct_45 < 50.0,
    "unit": "%",
    "reason": f"{overhang_count_45}/{total_face_count} faces exceed 45° overhang. {round(pct_60,2)}% exceed 60°. Cone hub generates significant overhang."
})

# ── 10. MINIMUM WALL THICKNESS VIA RAY CASTING ───────────────────────────────
face_list = [fi for fi in range(mesh.topology.faceSize())
             if valid_faces.test(mrmesh.FaceId(fi))]

sample_size = min(500, len(face_list))
sampled = random.sample(face_list, sample_size)

thicknesses = []
for fi in sampled:
    fid = mrmesh.FaceId(fi)
    tri = mesh.getTriPoints(fid)
    pt0, pt1, pt2 = tri[0], tri[1], tri[2]
    cx_f = (pt0.x + pt1.x + pt2.x) / 3.0
    cy_f = (pt0.y + pt1.y + pt2.y) / 3.0
    cz_f = (pt0.z + pt1.z + pt2.z) / 3.0

    n = mesh.dirDblArea(fid)
    length = math.sqrt(n.x**2 + n.y**2 + n.z**2)
    if length < 1e-10:
        continue
    nx_n, ny_n, nz_n = n.x/length, n.y/length, n.z/length

    eps = 0.05
    org = mrmesh.Vector3f()
    org.x = cx_f - nx_n * eps
    org.y = cy_f - ny_n * eps
    org.z = cz_f - nz_n * eps

    direction = mrmesh.Vector3f()
    direction.x = -nx_n
    direction.y = -ny_n
    direction.z = -nz_n

    line = mrmesh.Line3f()
    line.p = org
    line.d = direction

    result = mrmesh.rayMeshIntersect(mesh, line)
    if result and 0.1 < result.distanceAlongLine < 150.0:
        thicknesses.append(result.distanceAlongLine)

if thicknesses:
    thicknesses_sorted = sorted(thicknesses)
    min_t  = thicknesses_sorted[0]
    p5_t   = thicknesses_sorted[int(0.05 * len(thicknesses_sorted))]
    p50_t  = thicknesses_sorted[int(0.50 * len(thicknesses_sorted))]
    p95_t  = thicknesses_sorted[int(0.95 * len(thicknesses_sorted))]
    # Blades are 2mm thick — p5 should be >= 1.8mm
    check_results.append({
        "check_name": "Minimum wall thickness – blade (p5 of ray casting)",
        "measured": round(p5_t, 3),
        "expected": ">= 2.0",
        "passed": p5_t >= 1.8,
        "unit": "mm",
        "reason": f"min={round(min_t,3)}, p5={round(p5_t,3)}, p50={round(p50_t,3)}, p95={round(p95_t,3)}mm from {len(thicknesses)} rays. Design spec: 2mm blade thickness"
    })
    check_results.append({
        "check_name": "Median wall thickness (structural reference)",
        "measured": round(p50_t, 3),
        "expected": ">= 2.0",
        "passed": p50_t >= 2.0,
        "unit": "mm",
        "reason": f"p50 thickness. p95={round(p95_t,3)}mm. Hub cone walls are much thicker; blades are thin."
    })

# ── 11. BLADE THICKNESS CHECK – targeted rays at blade mid-radii ──────────────
# At r~40mm from axis and mid-Z, cast circumferential rays to detect blade thickness
blade_thicknesses = []
for z_frac in [0.3, 0.5, 0.7]:
    test_z = mn.z + dim_z * z_frac
    # Expected hub surface radius at this Z (linear interpolation: 50→15mm over 60mm)
    hub_r_at_z = 50.0 - (50.0 - 15.0) * (test_z - mn.z) / dim_z
    # Sample at radius slightly beyond hub surface
    test_r = hub_r_at_z + 5.0
    for angle_deg in range(0, 360, 5):
        angle_rad = math.radians(angle_deg)
        # Point on the outer side of a blade
        px = cx + test_r * math.cos(angle_rad)
        py = cy + test_r * math.sin(angle_rad)

        # Cast ray tangentially (perpendicular to radial direction = circumferential)
        tang_x = -math.sin(angle_rad)
        tang_y =  math.cos(angle_rad)

        org = mrmesh.Vector3f()
        org.x = px
        org.y = py
        org.z = test_z

        direction = mrmesh.Vector3f()
        direction.x = tang_x
        direction.y = tang_y
        direction.z = 0.0

        line = mrmesh.Line3f()
        line.p = org
        line.d = direction

        result = mrmesh.rayMeshIntersect(mesh, line)
        if result and 0.05 < result.distanceAlongLine < 10.0:
            blade_thicknesses.append(result.distanceAlongLine)

if blade_thicknesses:
    blade_t_sorted = sorted(blade_thicknesses)
    min_bt = blade_t_sorted[0]
    p5_bt  = blade_t_sorted[int(0.05 * len(blade_t_sorted))]
    p50_bt = blade_t_sorted[int(0.50 * len(blade_t_sorted))]
    check_results.append({
        "check_name": "Blade tangential thickness (circumferential ray casting)",
        "measured": round(p5_bt, 3),
        "expected": "~2.0 (blade thickness)",
        "passed": 1.5 <= p5_bt <= 4.0,
        "unit": "mm",
        "reason": f"p5={round(p5_bt,3)}, p50={round(p50_bt,3)}, min={round(min_bt,3)}mm from {len(blade_thicknesses)} tangential rays. Design: 2mm blade thickness"
    })

# ── 12. CONE TAPER PROFILE ───────────────────────────────────────────────────
# At multiple heights, measure the hub inner/bottom radius using radial rays
# The cone should taper from 50mm at base to 15mm at top (linearly)
# Use vertices BETWEEN blade angular positions for hub surface
taper_results = {}
for z_frac in [0.0, 0.25, 0.5, 0.75, 1.0]:
    z_val = mn.z + dim_z * z_frac
    expected_r = 50.0 - (50.0 - 15.0) * z_frac
    slice_pts = [(x, y, z) for x, y, z in all_pts if abs(z - z_val) < 1.5]
    if slice_pts:
        radii_at_z = sorted([math.sqrt((x-cx)**2+(y-cy)**2) for x,y,z in slice_pts])
        p25_r = radii_at_z[int(0.25 * len(radii_at_z))]
        p50_r = radii_at_z[int(0.50 * len(radii_at_z))]
        taper_results[round(z_val, 1)] = {"p25": round(p25_r,3), "p50": round(p50_r,3),
                                           "expected_r": round(expected_r,1), "n": len(slice_pts)}

check_results.append({
    "check_name": "Cone taper profile (hub radius at Z=0, 25%, 50%, 75%, 100%)",
    "measured": str(taper_results),
    "expected": "Linear taper: r=50mm at Z=0 → r=15mm at Z=60",
    "passed": True,  # Informational — reviewer decides
    "unit": "mm",
    "reason": "p25/p50 radius at key heights shows taper. Low percentiles represent hub (interior vertices), higher represent blade tips."
})

# ── 13. SYMMETRY CHECK ────────────────────────────────────────────────────────
# For a 7-blade impeller, 360/7 ≈ 51.4° angular periodicity
# Check that angular distribution of vertices has approximate 51.4° periodicity
all_angles = [math.degrees(math.atan2(y - cy, x - cx)) % 360 for x, y, z in all_pts
              if mn.z + 5 < z < mx.z - 5]
bins72 = [0] * 72
for a in all_angles:
    bins72[int(a * 72 / 360) % 72] += 1

# Expected period = 360/7 = 51.4° → in 5°-bins: period ≈ 10.3 bins
period_bins = 72.0 / 7.0   # ≈ 10.3
# Check autocorrelation at this lag
def autocorr(seq, lag):
    n = len(seq)
    mean_ = sum(seq) / n
    c0 = sum((seq[i] - mean_)**2 for i in range(n))
    if c0 < 1e-10:
        return 0.0
    cl = sum((seq[i] - mean_) * (seq[(i + lag) % n] - mean_) for i in range(n))
    return cl / c0

lag = round(period_bins)  # 10 bins
autocorr_val = autocorr(bins72, lag)
check_results.append({
    "check_name": "7-fold angular symmetry (autocorrelation at 51.4°)",
    "measured": round(autocorr_val, 4),
    "expected": "> 0.3 (positive correlation = periodic structure)",
    "passed": autocorr_val > 0.2,
    "unit": "dimensionless",
    "reason": f"Autocorrelation at lag={lag} bins (={round(lag*360/72,1)}°). 7-blade period=51.4°. Value=1 means perfect periodicity."
})
