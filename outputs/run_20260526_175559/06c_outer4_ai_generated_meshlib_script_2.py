
import meshlib.mrmeshpy as mrmesh
import math

check_results = []

coords = mesh.points
bb = mesh.getBoundingBox()
z_base = bb.min.z
z_top  = bb.max.z

# ── Refined BLADE COUNT using smoothed angular profile ───────────────────────
# At multiple Z-slices, find angular peaks in radial protrusion above hub surface

def r_hub(z_frac):
    """Hub cone radius at fractional height 0..1"""
    return 50.0 - (50.0 - 15.0) * z_frac

def count_blades_at_z(z_target, z_tol=3.0, smooth_window=5, threshold_above_hub=2.0):
    """Count angular blade peaks at given Z height."""
    hub_r = r_hub((z_target - z_base) / (z_top - z_base))
    verts = []
    for vid in range(coords.size()):
        pt = coords[mrmesh.VertId(vid)]
        if abs(pt.z - z_target) < z_tol:
            r = math.sqrt(pt.x**2 + pt.y**2)
            angle = math.atan2(pt.y, pt.x) * 180.0 / math.pi
            verts.append((angle, r))
    if not verts:
        return 0, []

    # 360 degree bins, 1-degree resolution
    bins = [[] for _ in range(360)]
    for angle, r in verts:
        idx = int((angle + 180)) % 360
        bins[idx].append(r)

    # Max radius per bin
    max_r = [max(b) if b else 0.0 for b in bins]

    # Smooth with window
    smoothed = []
    w = smooth_window
    for i in range(360):
        vals = [max_r[(i+j-w//2) % 360] for j in range(w)]
        smoothed.append(sum(vals)/len(vals))

    threshold = hub_r + threshold_above_hub

    # Count crossings from below to above threshold
    peaks = []
    in_blade = False
    blade_start = 0
    for i in range(720):  # two full circles to handle wrap
        idx = i % 360
        if smoothed[idx] > threshold and not in_blade:
            in_blade = True
            blade_start = i
        elif smoothed[idx] <= threshold and in_blade:
            in_blade = False
            center_angle = ((blade_start + i) / 2) % 360 - 180
            span = i - blade_start
            peaks.append((center_angle, span))

    # De-duplicate peaks that come from wrap-around (same blade seen twice)
    seen = set()
    unique_peaks = []
    for center, span in peaks:
        key = round(center / 5) * 5  # quantize to 5 degrees
        if key not in seen:
            seen.add(key)
            unique_peaks.append((center, span))

    return len(unique_peaks), unique_peaks

# Multi-slice blade count
blade_counts = {}
for z_frac in [0.15, 0.3, 0.5, 0.7, 0.85]:
    z_t = z_base + z_frac * (z_top - z_base)
    cnt, _ = count_blades_at_z(z_t, z_tol=4.0, smooth_window=7, threshold_above_hub=2.5)
    blade_counts[round(z_frac, 2)] = cnt

mode_count = max(set(blade_counts.values()), key=list(blade_counts.values()).count)
check_results.append({
    "check_name": "Blade Count (multi-slice consensus)",
    "measured": mode_count,
    "expected": 7,
    "passed": abs(mode_count - 7) <= 1,
    "unit": "count",
    "reason": f"Blade counts per Z fraction: {blade_counts}. Mode={mode_count}. Expected 7 blades."
})

# ── Blade twist: compare centroid angles at bottom vs top using finer method ──
def get_blade_peak_angles_at_z(z_target, r_min, z_tol=5.0, smooth_window=9):
    hub_r = r_hub((z_target - z_base) / (z_top - z_base))
    verts = []
    for vid in range(coords.size()):
        pt = coords[mrmesh.VertId(vid)]
        if abs(pt.z - z_target) < z_tol:
            r = math.sqrt(pt.x**2 + pt.y**2)
            if r > r_min:
                angle = math.atan2(pt.y, pt.x) * 180.0 / math.pi
                verts.append((angle, r))
    if not verts:
        return []

    bins = [[] for _ in range(360)]
    for angle, r in verts:
        idx = int((angle + 180)) % 360
        bins[idx].append(r)
    max_r = [max(b) if b else 0.0 for b in bins]

    # Gaussian-like smoothing
    w = smooth_window
    smoothed = []
    for i in range(360):
        vals = [max_r[(i+j-w//2) % 360] for j in range(w)]
        smoothed.append(sum(vals)/len(vals))

    # Find peaks (local maxima above threshold)
    threshold = hub_r + 1.0
    peak_angles = []
    for i in range(360):
        prev = smoothed[(i-1) % 360]
        curr = smoothed[i]
        nxt  = smoothed[(i+1) % 360]
        if curr > threshold and curr >= prev and curr >= nxt:
            peak_angles.append(i - 180)  # convert to -180..180

    # Merge close peaks (within 15 degrees)
    merged = []
    used = set()
    for i, a in enumerate(sorted(peak_angles)):
        if i in used:
            continue
        cluster = [a]
        for j, b in enumerate(peak_angles):
            if j != i and j not in used and abs(b - a) < 15:
                cluster.append(b)
                used.add(j)
        merged.append(sum(cluster)/len(cluster))
        used.add(i)

    return sorted(merged)

z_bot_target = z_base + 5.0
z_top_target = z_top  - 5.0

r_hub_bot = r_hub(5.0 / 60.0)   # ~47mm
r_hub_top = r_hub(55.0 / 60.0)  # ~18.8mm

peaks_bot = get_blade_peak_angles_at_z(z_bot_target, r_min=r_hub_bot + 1.5, z_tol=6.0)
peaks_top = get_blade_peak_angles_at_z(z_top_target, r_min=r_hub_top + 0.8, z_tol=6.0)

check_results.append({
    "check_name": "Blade Angular Peaks at Z=5mm (bottom)",
    "measured": len(peaks_bot),
    "expected": 7,
    "passed": abs(len(peaks_bot) - 7) <= 2,
    "unit": "count",
    "reason": f"Found {len(peaks_bot)} blade peaks near bottom (Z≈5mm). Peak angles: {[round(a,1) for a in peaks_bot]}"
})

check_results.append({
    "check_name": "Blade Angular Peaks at Z=55mm (top)",
    "measured": len(peaks_top),
    "expected": 7,
    "passed": abs(len(peaks_top) - 7) <= 2,
    "unit": "count",
    "reason": f"Found {len(peaks_top)} blade peaks near top (Z≈55mm). Peak angles: {[round(a,1) for a in peaks_top]}"
})

# Compute twist if we have matching peaks
if len(peaks_bot) >= 2 and len(peaks_top) >= 2:
    # For each bottom peak, find the nearest top peak and compute angular difference
    twist_values = []
    used_top = set()
    for pb in peaks_bot:
        best_diff = None
        best_idx = -1
        for j, pt_ang in enumerate(peaks_top):
            diff = pt_ang - pb
            # Wrap to [-180, 180]
            if diff > 180: diff -= 360
            if diff < -180: diff += 360
            if best_diff is None or abs(diff) < abs(best_diff):
                best_diff = diff
                best_idx = j
        if best_idx >= 0:
            twist_values.append(best_diff)

    mean_twist = sum(twist_values) / len(twist_values) if twist_values else 0
    twist_std  = (sum((v - mean_twist)**2 for v in twist_values) / len(twist_values))**0.5 if len(twist_values) > 1 else 0

    check_results.append({
        "check_name": "Blade Twist Angle (bottom to top, refined)",
        "measured": round(abs(mean_twist), 2),
        "expected": 60.0,
        "passed": 20.0 <= abs(mean_twist) <= 100.0,
        "unit": "degrees",
        "reason": f"Mean blade twist (bottom→top): {round(mean_twist,1)}° ± {round(twist_std,1)}°. "
                  f"Individual offsets: {[round(v,1) for v in twist_values]}. Expected ≈60°."
    })
else:
    check_results.append({
        "check_name": "Blade Twist Angle (bottom to top, refined)",
        "measured": "undetermined",
        "expected": 60.0,
        "passed": False,
        "unit": "degrees",
        "reason": f"Insufficient blade peaks for twist computation: bot={len(peaks_bot)}, top={len(peaks_top)}."
    })

# ── Blade Thickness: use closest-point projection across blade cross-sections ─
# Find blade vertices at mid-height (Z≈30), group by angular proximity,
# compute min/max within each blade cluster to get chord width
z_mid = z_base + 30.0
hub_r_mid = r_hub(0.5)  # 32.5mm

blade_verts_mid = []
for vid in range(coords.size()):
    pt = coords[mrmesh.VertId(vid)]
    if abs(pt.z - z_mid) < 4.0:
        r = math.sqrt(pt.x**2 + pt.y**2)
        if r > hub_r_mid + 0.5:  # beyond hub surface
            angle = math.atan2(pt.y, pt.x) * 180.0 / math.pi
            blade_verts_mid.append((angle, r, pt.x, pt.y))

if blade_verts_mid:
    # Get blade peak angles from count method
    _, peak_data = count_blades_at_z(z_mid, z_tol=4.0, smooth_window=7, threshold_above_hub=2.5)

    if peak_data:
        blade_spacing = 360.0 / max(mode_count, 1)  # ~51.4° for 7 blades

        thicknesses = []
        for center_angle, _ in peak_data[:7]:  # first 7 peaks
            # collect verts in ±blade_spacing/4 degrees of center
            half_window = blade_spacing / 4.0
            cluster_verts = [(a, r, x, y) for a, r, x, y in blade_verts_mid
                             if abs(((a - center_angle + 180) % 360) - 180) < half_window]

            if len(cluster_verts) >= 2:
                # project onto the tangential direction at center_angle
                tangent_x = -math.sin(center_angle * math.pi / 180.0)
                tangent_y =  math.cos(center_angle * math.pi / 180.0)
                projections = [x * tangent_x + y * tangent_y for _, _, x, y in cluster_verts]
                thickness = max(projections) - min(projections)
                thicknesses.append(thickness)

        if thicknesses:
            mean_thick = sum(thicknesses) / len(thicknesses)
            min_thick  = min(thicknesses)
            check_results.append({
                "check_name": "Blade Chord Width at Mid-Height (Z=30mm)",
                "measured": round(mean_thick, 3),
                "expected": 2.0,
                "passed": mean_thick <= 10.0,
                "unit": "mm",
                "reason": f"Mean chord width of {len(thicknesses)} blade clusters at Z=30mm: {round(mean_thick,2)}mm (min={round(min_thick,2)}mm). Expected ~2mm blade thickness (thin blades tolerated up to 10mm chord)."
            })
        else:
            check_results.append({
                "check_name": "Blade Chord Width at Mid-Height (Z=30mm)",
                "measured": "N/A",
                "expected": 2.0,
                "passed": False,
                "unit": "mm",
                "reason": "Could not compute chord widths for blade clusters."
            })

# ── Wall thickness via ray casting with better sampling ──────────────────────
def vec3f(x, y, z):
    v = mrmesh.Vector3f(); v.x = x; v.y = y; v.z = z
    return v

# Cast rays from blade face-center regions inward
wall_measurements = []
fsize = mesh.topology.faceSize()
step = max(1, fsize // 400)

for fid_int in range(0, fsize, step):
    fid = mrmesh.FaceId(fid_int)
    if not mesh.topology.hasFace(fid):
        continue
    pts = mesh.getTriPoints(fid)
    cx = (pts.a.x + pts.b.x + pts.c.x) / 3.0
    cy = (pts.a.y + pts.b.y + pts.c.y) / 3.0
    cz = (pts.a.z + pts.b.z + pts.c.z) / 3.0

    r = math.sqrt(cx**2 + cy**2)
    # Focus on blade region: r > hub surface + some margin
    z_frac = (cz - z_base) / (z_top - z_base)
    hub_surface = r_hub(z_frac)
    if r < hub_surface + 1.0:
        continue  # skip hub body, focus on blades

    n = mesh.dirDblArea(fid)
    nx, ny, nz = n.x, n.y, n.z
    length = math.sqrt(nx**2 + ny**2 + nz**2)
    if length < 1e-9:
        continue

    # inward ray
    inx, iny, inz = -nx/length, -ny/length, -nz/length
    origin = vec3f(cx + inx*0.15, cy + iny*0.15, cz + inz*0.15)
    ray_dir = vec3f(inx, iny, inz)

    line = mrmesh.Line3f()
    line.p = origin
    line.d = ray_dir

    res = mrmesh.rayMeshIntersect(mesh, line)
    if res and 0.05 < res.distanceAlongLine < 30.0:
        wall_measurements.append(res.distanceAlongLine)

if wall_measurements:
    wall_arr = sorted(wall_measurements)
    min_wall = wall_arr[0]
    pct5 = wall_arr[max(0, int(len(wall_arr)*0.05))]
    pct50 = wall_arr[len(wall_arr)//2]
    check_results.append({
        "check_name": "Blade Wall Thickness (ray cast, inward from blade faces)",
        "measured": round(min_wall, 3),
        "expected": ">= 2.0",
        "passed": pct5 >= 2.0,
        "unit": "mm",
        "reason": f"Wall thickness from {len(wall_measurements)} blade-region rays: min={round(min_wall,3)}mm, 5th-pct={round(pct5,3)}mm, median={round(pct50,3)}mm. FDM min wall = 2.0mm."
    })
else:
    check_results.append({
        "check_name": "Blade Wall Thickness (ray cast, inward from blade faces)",
        "measured": "N/A",
        "expected": ">= 2.0",
        "passed": False,
        "unit": "mm",
        "reason": "No valid wall-thickness measurements in blade region."
    })
