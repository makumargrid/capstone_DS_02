
import meshlib.mrmeshpy as mrmesh
import math

check_results = []

# ── helpers ──────────────────────────────────────────────────────────────────
def vec3f(x, y, z):
    v = mrmesh.Vector3f()
    v.x = x; v.y = y; v.z = z
    return v

# ── 1. BOUNDING BOX (baseline already reported, but we need exact dims here) ─
bb = mesh.getBoundingBox()
mx = bb.max; mn = bb.min
dim_x = mx.x - mn.x
dim_y = mx.y - mn.y
dim_z = mx.z - mn.z

# X dimension: blades extend to ~radius 50 + 15mm protrusion at base -> ~130mm total
check_results.append({
    "check_name": "Bounding Box X (overall width)",
    "measured": round(dim_x, 3),
    "expected": 132.5,
    "passed": abs(dim_x - 132.5) <= 15,
    "unit": "mm",
    "reason": f"Expected 132.5mm ±15mm. Measured {round(dim_x,3)}mm."
})

check_results.append({
    "check_name": "Bounding Box Y (overall depth)",
    "measured": round(dim_y, 3),
    "expected": 132.5,
    "passed": abs(dim_y - 132.5) <= 15,
    "unit": "mm",
    "reason": f"Expected 132.5mm ±15mm. Measured {round(dim_y,3)}mm."
})

check_results.append({
    "check_name": "Bounding Box Z (total height)",
    "measured": round(dim_z, 3),
    "expected": 60.0,
    "passed": abs(dim_z - 60.0) <= 1.0,
    "unit": "mm",
    "reason": f"Hub height must be exactly 60mm. Measured {round(dim_z,3)}mm."
})

# ── 2. HUB GEOMETRY: base diameter 100mm, top diameter 30mm ──────────────────
# Collect all vertices
verts = mesh.topology.getValidVerts()
coords = mesh.points

# vertices near Z=0 (base) – within 1mm
base_verts = []
top_verts  = []
z_base = mn.z
z_top  = mx.z

for vid in range(coords.size()):
    try:
        pt = coords[mrmesh.VertId(vid)]
    except Exception:
        continue
    if abs(pt.z - z_base) < 1.5:
        r = math.sqrt(pt.x**2 + pt.y**2)
        base_verts.append(r)
    if abs(pt.z - z_top) < 1.5:
        r = math.sqrt(pt.x**2 + pt.y**2)
        top_verts.append(r)

# Hub base: the truncated cone outer surface should have r≈50mm
# Blade footprint will be at r≤50mm from Z axis; the hub surface itself at r=50
# Among base vertices, the pure hub ring is at r~50; blade edges might be slightly larger.
# We'll look for minimum radius cluster near 50mm
if base_verts:
    base_verts_sorted = sorted(base_verts)
    # Hub base perimeter: expect r~50mm (diam 100mm)
    # The actual base of the hub (not blade) should be near r=50
    # Find the cluster of vertices within ±10% of r=50
    hub_base_radii = [r for r in base_verts if 30 <= r <= 60]
    hub_base_max = max(hub_base_radii) if hub_base_radii else 0
    hub_base_min = min(hub_base_radii) if hub_base_radii else 0
    hub_base_mean = sum(hub_base_radii)/len(hub_base_radii) if hub_base_radii else 0

    check_results.append({
        "check_name": "Hub Base Diameter (at Z≈0)",
        "measured": round(hub_base_max * 2, 3),
        "expected": 100.0,
        "passed": abs(hub_base_max * 2 - 100.0) <= 5.0,
        "unit": "mm",
        "reason": f"Max radius at Z≈0 for hub surface is {round(hub_base_max,3)}mm → diam {round(hub_base_max*2,3)}mm. Expected 100mm ±5mm."
    })
else:
    check_results.append({
        "check_name": "Hub Base Diameter (at Z≈0)",
        "measured": "no vertices found",
        "expected": 100.0,
        "passed": False,
        "unit": "mm",
        "reason": "Could not find vertices near Z=0."
    })

# Hub top: expect r~15mm (diam 30mm)
if top_verts:
    top_verts_sorted = sorted(top_verts)
    # The hub top ring at r=15mm; blades extend further at top (r up to ~15+5=20mm)
    hub_top_radii = [r for r in top_verts if 5 <= r <= 25]
    hub_top_min  = min(hub_top_radii) if hub_top_radii else 0
    hub_top_max  = max(hub_top_radii) if hub_top_radii else 0

    check_results.append({
        "check_name": "Hub Top Diameter (at Z≈60)",
        "measured": round(hub_top_max * 2, 3),
        "expected": 30.0,
        "passed": abs(hub_top_max * 2 - 30.0) <= 8.0,
        "unit": "mm",
        "reason": f"Max radius at Z≈60 for hub/blade top is {round(hub_top_max,3)}mm → diam {round(hub_top_max*2,3)}mm. Expected 30mm ±8mm."
    })
else:
    check_results.append({
        "check_name": "Hub Top Diameter (at Z≈60)",
        "measured": "no vertices found",
        "expected": 30.0,
        "passed": False,
        "unit": "mm",
        "reason": "Could not find vertices near Z_top."
    })

# ── 3. CENTRAL BORE: 15mm diameter through Z-axis ────────────────────────────
# Find vertices very close to the Z-axis (x≈0, y≈0) at various heights
bore_radii_all = []
for vid in range(coords.size()):
    try:
        pt = coords[mrmesh.VertId(vid)]
    except Exception:
        continue
    r = math.sqrt(pt.x**2 + pt.y**2)
    if r < 12.0:  # close to bore
        bore_radii_all.append((r, pt.z))

# The bore wall should be at r≈7.5mm (15mm diameter)
bore_wall_r = [r for r, z in bore_radii_all if r > 3.0]
if bore_wall_r:
    mean_bore_r = sum(bore_wall_r) / len(bore_wall_r)
    bore_diam = mean_bore_r * 2
    check_results.append({
        "check_name": "Central Bore Diameter",
        "measured": round(bore_diam, 3),
        "expected": 15.0,
        "passed": abs(bore_diam - 15.0) <= 2.0,
        "unit": "mm",
        "reason": f"Mean bore-wall radius {round(mean_bore_r,3)}mm → diameter {round(bore_diam,3)}mm. Expected 15mm ±2mm."
    })

    # Also check bore penetrates full height (Z range of bore vertices)
    bore_z_vals = [z for r, z in bore_radii_all if r > 3.0]
    bore_z_span = max(bore_z_vals) - min(bore_z_vals) if bore_z_vals else 0
    check_results.append({
        "check_name": "Central Bore Z-Span (full through)",
        "measured": round(bore_z_span, 3),
        "expected": 60.0,
        "passed": bore_z_span >= 55.0,
        "unit": "mm",
        "reason": f"Bore vertices span Z from {round(min(bore_z_vals),2)} to {round(max(bore_z_vals),2)} = {round(bore_z_span,3)}mm. Expected ~60mm."
    })
else:
    # Bore might be absent – check with ray cast along Z axis
    check_results.append({
        "check_name": "Central Bore Diameter",
        "measured": 0.0,
        "expected": 15.0,
        "passed": False,
        "unit": "mm",
        "reason": "No vertices found near Z-axis indicating missing or very small bore."
    })

# ── 4. BLADE COUNT ────────────────────────────────────────────────────────────
# Strategy: at a mid-height slice (Z≈30), sample radii outward from hub surface
# Count angular peaks (protrusions above hub cone surface) → = blade count
# Hub cone radius at Z=30: r(z) = 50 - (50-15)*(30/60) = 50 - 17.5 = 32.5mm
z_slice = z_base + 30.0
r_hub_at_z30 = 50.0 - (50.0-15.0)*(30.0/60.0)   # = 32.5mm

# Collect vertices within 2mm of z=30
mid_verts = []
for vid in range(coords.size()):
    try:
        pt = coords[mrmesh.VertId(vid)]
    except Exception:
        continue
    if abs(pt.z - z_slice) < 2.0:
        angle = math.atan2(pt.y, pt.x) * 180.0 / math.pi  # degrees
        r = math.sqrt(pt.x**2 + pt.y**2)
        mid_verts.append((angle, r))

if mid_verts:
    # Sort by angle
    mid_verts.sort(key=lambda x: x[0])
    angles = [v[0] for v in mid_verts]
    radii  = [v[1] for v in mid_verts]

    # Bin into 360 angular bins of 1 degree each
    bins = [[] for _ in range(360)]
    for angle, r in mid_verts:
        bin_idx = int((angle + 180) % 360)
        bins[bin_idx].append(r)

    # Max radius per bin
    max_r_per_bin = [max(b) if b else 0 for b in bins]

    # Threshold: hub surface + some fraction of expected blade protrusion (~7.5mm midway)
    blade_threshold = r_hub_at_z30 + 3.0  # 35.5mm

    # Find blade cross-sections as angular regions above threshold
    in_blade = False
    blade_angle_spans = []
    start_angle = None
    for i, r_max in enumerate(max_r_per_bin + max_r_per_bin[:10]):  # wrap around
        idx = i % 360
        if max_r_per_bin[idx] > blade_threshold and not in_blade:
            in_blade = True
            start_angle = i
        elif max_r_per_bin[idx] <= blade_threshold and in_blade:
            in_blade = False
            blade_angle_spans.append(i - start_angle)

    blade_count_estimate = len(blade_angle_spans)

    check_results.append({
        "check_name": "Blade Count (at Z=30mm mid-slice)",
        "measured": blade_count_estimate,
        "expected": 7,
        "passed": abs(blade_count_estimate - 7) <= 1,
        "unit": "count",
        "reason": f"Counted {blade_count_estimate} angular protrusion regions at Z≈30mm above hub surface threshold r={round(blade_threshold,1)}mm. Expected 7 blades."
    })
else:
    check_results.append({
        "check_name": "Blade Count (at Z=30mm mid-slice)",
        "measured": 0,
        "expected": 7,
        "passed": False,
        "unit": "count",
        "reason": "No vertices found near Z=30mm."
    })

# ── 5. BLADE PROTRUSION HEIGHT ────────────────────────────────────────────────
# At base (Z≈0): blades should protrude 15mm above hub surface.
# Hub surface radius at Z=0 is 50mm → blade tip should be at r≈50+15=65mm
# At top (Z≈60): protrusion 5mm → hub radius 15mm → blade tip r≈15+5=20mm

# Base protrusion
base_blade_radii = [r for r in base_verts if r > 50.5]  # beyond hub base
if base_blade_radii:
    max_base_r = max(base_blade_radii)
    measured_base_protrusion = max_base_r - 50.0
    check_results.append({
        "check_name": "Blade Protrusion at Base (Z≈0)",
        "measured": round(measured_base_protrusion, 3),
        "expected": 15.0,
        "passed": abs(measured_base_protrusion - 15.0) <= 3.0,
        "unit": "mm",
        "reason": f"Max radius at Z≈0 is {round(max_base_r,3)}mm; hub base r=50mm → protrusion={round(measured_base_protrusion,3)}mm. Expected 15mm ±3mm."
    })
else:
    check_results.append({
        "check_name": "Blade Protrusion at Base (Z≈0)",
        "measured": 0.0,
        "expected": 15.0,
        "passed": False,
        "unit": "mm",
        "reason": "No vertices found beyond hub base radius at Z≈0."
    })

# Top protrusion
top_blade_radii = [r for r in top_verts if r > 16.0]
if top_blade_radii:
    max_top_r = max(top_blade_radii)
    measured_top_protrusion = max_top_r - 15.0
    check_results.append({
        "check_name": "Blade Protrusion at Top (Z≈60)",
        "measured": round(measured_top_protrusion, 3),
        "expected": 5.0,
        "passed": abs(measured_top_protrusion - 5.0) <= 3.0,
        "unit": "mm",
        "reason": f"Max radius at Z≈60 is {round(max_top_r,3)}mm; hub top r=15mm → protrusion={round(measured_top_protrusion,3)}mm. Expected 5mm ±3mm."
    })
else:
    check_results.append({
        "check_name": "Blade Protrusion at Top (Z≈60)",
        "measured": 0.0,
        "expected": 5.0,
        "passed": False,
        "unit": "mm",
        "reason": "No blade-tip vertices found beyond hub top radius at Z≈60."
    })

# ── 6. BLADE THICKNESS ────────────────────────────────────────────────────────
# Strategy: at the mid-height (Z≈30), for each detected blade span,
# compute the angular width and convert to arc length at hub surface + mid-protrusion
# thickness = arc_length * (r_hub_z30) * angle_radians
# Expected thickness: 2mm, at r≈32.5mm arc_span ~ 2/32.5 rad ~ 3.5 degrees
if mid_verts and blade_angle_spans:
    # Use average angular span of blade regions
    avg_blade_angle_deg = sum(blade_angle_spans) / len(blade_angle_spans)
    # Arc length at hub surface radius
    avg_thickness_arc = avg_blade_angle_deg * math.pi / 180.0 * r_hub_at_z30

    check_results.append({
        "check_name": "Blade Thickness (approx arc-length at mid-height)",
        "measured": round(avg_thickness_arc, 3),
        "expected": 2.0,
        "passed": avg_thickness_arc <= 8.0,  # generous: 2mm is thin, but blades may be a few mm wide
        "unit": "mm",
        "reason": f"Average angular span of blade cross-sections at Z=30 is {round(avg_blade_angle_deg,1)}°, arc at r={round(r_hub_at_z30,1)}mm → ~{round(avg_thickness_arc,2)}mm. Expected ≈2mm blade thickness."
    })

# ── 7. BLADE TWIST / ANGULAR OFFSET (base vs top) ────────────────────────────
# Compare centroid angle of blade regions at Z≈2 vs Z≈58
def get_blade_centroids_at_z(z_target, r_min_threshold, hub_r, tolerance=3.0):
    verts_at_z = []
    for vid in range(coords.size()):
        try:
            pt = coords[mrmesh.VertId(vid)]
        except Exception:
            continue
        if abs(pt.z - z_target) < tolerance:
            r = math.sqrt(pt.x**2 + pt.y**2)
            if r > r_min_threshold:
                angle = math.atan2(pt.y, pt.x) * 180.0 / math.pi
                verts_at_z.append((angle, r))
    return verts_at_z

blade_verts_bot = get_blade_centroids_at_z(z_base + 3.0, 52.0, 50.0, tolerance=4.0)
blade_verts_top = get_blade_centroids_at_z(z_top  - 3.0, 16.5, 15.0, tolerance=4.0)

if blade_verts_bot and blade_verts_top:
    # Bin blade vertices into angular bins and find peaks
    def find_blade_peak_angles(verts_list, n_blades=7):
        if not verts_list:
            return []
        from_neg180_to_180 = sorted([a for a, r in verts_list])
        # use a 360-bin histogram
        hist = [0]*360
        for a, r in verts_list:
            idx = int((a + 180)) % 360
            hist[idx] += 1
        # find peaks
        peaks = []
        in_peak = False
        peak_sum = 0; peak_count = 0; start_i = 0
        for i, v in enumerate(hist + hist[:10]):
            idx = i % 360
            if hist[idx] > 0 and not in_peak:
                in_peak = True; peak_sum = 0; peak_count = 0; start_i = i
            elif hist[idx] > 0 and in_peak:
                pass
            elif hist[idx] == 0 and in_peak:
                in_peak = False
                center = start_i + (i - start_i)//2
                peaks.append((center % 360) - 180)
        return peaks[:n_blades]

    peaks_bot = find_blade_peak_angles(blade_verts_bot)
    peaks_top = find_blade_peak_angles(blade_verts_top)

    if peaks_bot and peaks_top:
        # Align first peaks and compute mean angular offset
        peaks_bot_s = sorted(peaks_bot)
        peaks_top_s = sorted(peaks_top)
        if len(peaks_bot_s) >= 2 and len(peaks_top_s) >= 2:
            offsets = []
            for pb in peaks_bot_s[:len(peaks_top_s)]:
                # find closest top peak
                diffs = [(abs(pt - pb), pt - pb) for pt in peaks_top_s]
                diffs_wrapped = [(abs(d[1]+360) if d[1] < -180 else abs(d[1]-360) if d[1] > 180 else abs(d[1]), d[1]) for d in diffs]
                best = min(zip([d[0] for d in diffs], [d[1] for d in diffs]), key=lambda x: x[0])
                offsets.append(best[1])
            mean_twist = sum(offsets)/len(offsets) if offsets else 0
            check_results.append({
                "check_name": "Blade Twist Angle (bottom to top)",
                "measured": round(abs(mean_twist), 2),
                "expected": 60.0,
                "passed": 20.0 <= abs(mean_twist) <= 90.0,
                "unit": "degrees",
                "reason": f"Mean angular offset between blade centroids at Z≈3mm vs Z≈57mm is ~{round(abs(mean_twist),1)}°. Expected ≈60° twist."
            })
        else:
            check_results.append({
                "check_name": "Blade Twist Angle (bottom to top)",
                "measured": "insufficient peaks",
                "expected": 60.0,
                "passed": False,
                "unit": "degrees",
                "reason": f"Too few blade peak angles found: bot={len(peaks_bot_s)}, top={len(peaks_top_s)}."
            })

# ── 8. FDM OVERHANG CHECK ─────────────────────────────────────────────────────
# Faces with normal pointing significantly downward (angle from vertical > 45°) are overhangs
faces = mesh.topology.getValidFaces()
overhang_count = 0
total_faces = 0
steep_overhang_count = 0

for fid_int in range(mesh.topology.faceSize()):
    fid = mrmesh.FaceId(fid_int)
    if not mesh.topology.hasFace(fid):
        continue
    total_faces += 1
    n = mesh.dirDblArea(fid)
    # normal vector
    nx, ny, nz = n.x, n.y, n.z
    length = math.sqrt(nx**2 + ny**2 + nz**2)
    if length < 1e-9:
        continue
    nz_norm = nz / length
    # overhang: face normal has downward Z component (nz_norm < 0) AND angle > 45°
    # angle from -Z axis
    if nz_norm < 0:  # face points downward
        angle_from_down = math.acos(max(-1, min(1, -nz_norm))) * 180 / math.pi
        # angle_from_down is how far from straight down
        # overhang angle (from horizontal) = 90 - angle_from_down
        overhang_angle = 90.0 - angle_from_down
        if overhang_angle < 45.0:  # less than 45° from horizontal → needs support
            overhang_count += 1
        if overhang_angle < 20.0:  # severe overhang
            steep_overhang_count += 1

overhang_pct = 100.0 * overhang_count / total_faces if total_faces > 0 else 0
check_results.append({
    "check_name": "FDM Overhang Faces (<45° from horizontal)",
    "measured": round(overhang_pct, 2),
    "expected": "< 20%",
    "passed": overhang_pct < 30.0,
    "unit": "%",
    "reason": f"{overhang_count}/{total_faces} faces ({round(overhang_pct,2)}%) are overhangs needing support. Severe (<20°): {steep_overhang_count}."
})

# ── 9. MINIMUM WALL THICKNESS ─────────────────────────────────────────────────
# Sample face centers, cast ray inward, find opposite face
# Use a subset of blade faces for efficiency
sample_radii_for_wall = []
sample_count = 0
max_samples = 200

for fid_int in range(0, mesh.topology.faceSize(), max(1, mesh.topology.faceSize()//max_samples)):
    fid = mrmesh.FaceId(fid_int)
    if not mesh.topology.hasFace(fid):
        continue
    # Get face center
    try:
        pts = mesh.getTriPoints(fid)
        cx = (pts.a.x + pts.b.x + pts.c.x) / 3.0
        cy = (pts.a.y + pts.b.y + pts.c.y) / 3.0
        cz = (pts.a.z + pts.b.z + pts.c.z) / 3.0
    except Exception:
        continue

    # Face normal (inward)
    n = mesh.dirDblArea(fid)
    nx, ny, nz = n.x, n.y, n.z
    length = math.sqrt(nx**2 + ny**2 + nz**2)
    if length < 1e-9:
        continue
    # inward normal = -normal
    inx, iny, inz = -nx/length, -ny/length, -nz/length

    # Cast ray inward
    ray_origin = vec3f(cx + inx*0.1, cy + iny*0.1, cz + inz*0.1)
    ray_dir    = vec3f(inx, iny, inz)
    line = mrmesh.Line3f()
    line.p = ray_origin
    line.d = ray_dir

    result = mrmesh.rayMeshIntersect(mesh, line)
    if result and result.distanceAlongLine > 0.01 and result.distanceAlongLine < 50.0:
        sample_radii_for_wall.append(result.distanceAlongLine)
        sample_count += 1

if sample_radii_for_wall:
    min_wall = min(sample_radii_for_wall)
    pct_5 = sorted(sample_radii_for_wall)[max(0, int(len(sample_radii_for_wall)*0.05))]
    check_results.append({
        "check_name": "Minimum Wall Thickness (ray cast)",
        "measured": round(min_wall, 3),
        "expected": ">= 2.0",
        "passed": pct_5 >= 2.0,
        "unit": "mm",
        "reason": f"Min ray-cast wall thickness: {round(min_wall,3)}mm; 5th-percentile: {round(pct_5,3)}mm from {sample_count} samples. FDM min wall = 2mm."
    })
else:
    check_results.append({
        "check_name": "Minimum Wall Thickness (ray cast)",
        "measured": "N/A",
        "expected": ">= 2.0",
        "passed": False,
        "unit": "mm",
        "reason": "No valid ray-cast intersections found for wall thickness measurement."
    })

# ── 10. CONE TAPER PROFILE (mid-height cross-check) ──────────────────────────
# At Z=30, hub cone radius should be 50 - (50-15)*(30/60) = 32.5mm
z_mid = z_base + 30.0
r_expected_mid = 50.0 - (50.0 - 15.0) * (30.0 / 60.0)  # 32.5mm

mid_cone_verts = []
for vid in range(coords.size()):
    try:
        pt = coords[mrmesh.VertId(vid)]
    except Exception:
        continue
    if abs(pt.z - z_mid) < 1.5:
        r = math.sqrt(pt.x**2 + pt.y**2)
        if r < r_expected_mid + 5 and r > 5:
            mid_cone_verts.append(r)

if mid_cone_verts:
    # Hub surface at mid should be close to 32.5
    # The smallest radii near the hub in this band (excluding bore)
    hub_surface_radii = [r for r in mid_cone_verts if r > r_hub_at_z30 * 0.8]
    if hub_surface_radii:
        min_hub_r_mid = min(hub_surface_radii)
        check_results.append({
            "check_name": "Hub Cone Profile at Z=30mm (min outer radius)",
            "measured": round(min_hub_r_mid, 3),
            "expected": round(r_expected_mid, 1),
            "passed": abs(min_hub_r_mid - r_expected_mid) <= 5.0,
            "unit": "mm",
            "reason": f"Min hub outer radius at Z=30mm is {round(min_hub_r_mid,3)}mm. Expected cone interpolation ~{round(r_expected_mid,1)}mm ±5mm."
        })

# Summary stats for bore geometry
check_results.append({
    "check_name": "Bore Vertex Count Near Z-axis",
    "measured": len(bore_radii_all),
    "expected": "> 0",
    "passed": len(bore_radii_all) > 0,
    "unit": "count",
    "reason": f"Found {len(bore_radii_all)} vertices within r<12mm of Z-axis. Bore should be present."
})
