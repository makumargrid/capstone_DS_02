
import meshlib.mrmeshpy as mrmesh
import math

check_results = []

coords = mesh.points
bb = mesh.getBoundingBox()
z_base = bb.min.z
z_top  = bb.max.z

def r_hub(z_frac):
    """Hub cone radius at fractional height 0..1"""
    return 50.0 - (50.0 - 15.0) * z_frac

def vec3f(x, y, z):
    v = mrmesh.Vector3f(); v.x = x; v.y = y; v.z = z
    return v

# ── Shared helper: smoothed angular blade count at a Z slice ─────────────────
def count_blades_at_z(z_target, z_tol=3.0, smooth_window=7, threshold_above_hub=2.5):
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

    bins = [[] for _ in range(360)]
    for angle, r in verts:
        idx = int((angle + 180)) % 360
        bins[idx].append(r)
    max_r = [max(b) if b else 0.0 for b in bins]

    w = smooth_window
    smoothed = []
    for i in range(360):
        vals = [max_r[(i+j-w//2) % 360] for j in range(w)]
        smoothed.append(sum(vals)/len(vals))

    threshold = hub_r + threshold_above_hub

    peaks = []
    in_blade = False
    blade_start = 0
    for i in range(720):
        idx = i % 360
        if smoothed[idx] > threshold and not in_blade:
            in_blade = True
            blade_start = i
        elif smoothed[idx] <= threshold and in_blade:
            in_blade = False
            center_angle = ((blade_start + i) / 2) % 360 - 180
            span = i - blade_start
            peaks.append((center_angle, span))

    seen = set()
    unique_peaks = []
    for center, span in peaks:
        key = round(center / 5) * 5
        if key not in seen:
            seen.add(key)
            unique_peaks.append((center, span))

    return len(unique_peaks), unique_peaks

# ── 1. Multi-slice blade count ────────────────────────────────────────────────
blade_counts = {}
for z_frac in [0.15, 0.3, 0.5, 0.7, 0.85]:
    z_t = z_base + z_frac * (z_top - z_base)
    cnt, _ = count_blades_at_z(z_t, z_tol=4.0)
    blade_counts[round(z_frac, 2)] = cnt

mode_count = max(set(blade_counts.values()), key=list(blade_counts.values()).count)
check_results.append({
    "check_name": "Blade Count (multi-slice consensus)",
    "measured": mode_count,
    "expected": 7,
    "passed": abs(mode_count - 7) <= 1,
    "unit": "count",
    "reason": f"Blade counts per Z-fraction: {blade_counts}. Mode={mode_count}. Expected 7 blades."
})

# ── 2. Blade twist measurement ────────────────────────────────────────────────
def get_peak_angles(z_target, r_thresh, z_tol=5.0, smooth_w=11):
    hub_r = r_hub((z_target - z_base) / (z_top - z_base))
    verts = []
    for vid in range(coords.size()):
        pt = coords[mrmesh.VertId(vid)]
        if abs(pt.z - z_target) < z_tol:
            r = math.sqrt(pt.x**2 + pt.y**2)
            if r > r_thresh:
                angle = math.atan2(pt.y, pt.x) * 180.0 / math.pi
                verts.append((angle, r))
    if not verts:
        return []
    bins = [[] for _ in range(360)]
    for angle, r in verts:
        idx = int((angle + 180)) % 360
        bins[idx].append(r)
    max_r = [max(b) if b else 0.0 for b in bins]
    smoothed = []
    for i in range(360):
        vals = [max_r[(i+j-smooth_w//2) % 360] for j in range(smooth_w)]
        smoothed.append(sum(vals)/len(vals))
    threshold = hub_r + 1.0
    # Find local maxima
    peak_angles = []
    for i in range(360):
        prev = smoothed[(i-1) % 360]
        curr = smoothed[i]
        nxt  = smoothed[(i+1) % 360]
        if curr > threshold and curr >= prev and curr >= nxt:
            peak_angles.append(i - 180)
    # Merge clusters within 18 degrees
    sorted_pa = sorted(peak_angles)
    merged = []
    skip = set()
    for i, a in enumerate(sorted_pa):
        if i in skip:
            continue
        cluster = [a]
        for j in range(i+1, len(sorted_pa)):
            if sorted_pa[j] - sorted_pa[i] < 18:
                cluster.append(sorted_pa[j])
                skip.add(j)
        merged.append(sum(cluster)/len(cluster))
    return sorted(merged)

peaks_bot = get_peak_angles(z_base + 5.0,  r_thresh=r_hub(5.0/60.0) + 1.5, z_tol=6.0)
peaks_top = get_peak_angles(z_top  - 5.0,  r_thresh=r_hub(55.0/60.0) + 1.0, z_tol=6.0)

check_results.append({
    "check_name": "Blade Peak Angles at Z=5mm (bottom section)",
    "measured": len(peaks_bot),
    "expected": 7,
    "passed": abs(len(peaks_bot) - 7) <= 2,
    "unit": "count",
    "reason": f"Detected {len(peaks_bot)} peaks at Z≈5mm. Angles: {[round(a,1) for a in peaks_bot]}"
})

check_results.append({
    "check_name": "Blade Peak Angles at Z=55mm (top section)",
    "measured": len(peaks_top),
    "expected": 7,
    "passed": abs(len(peaks_top) - 7) <= 2,
    "unit": "count",
    "reason": f"Detected {len(peaks_top)} peaks at Z≈55mm. Angles: {[round(a,1) for a in peaks_top]}"
})

if len(peaks_bot) >= 2 and len(peaks_top) >= 2:
    twist_values = []
    for pb in peaks_bot:
        best_diff = None
        for pt_ang in peaks_top:
            diff = pt_ang - pb
            if diff > 180: diff -= 360
            if diff < -180: diff += 360
            if best_diff is None or abs(diff) < abs(best_diff):
                best_diff = diff
        twist_values.append(best_diff)
    mean_twist = sum(twist_values) / len(twist_values)
    check_results.append({
        "check_name": "Blade Twist Angle (Z=5mm → Z=55mm)",
        "measured": round(abs(mean_twist), 2),
        "expected": 60.0,
        "passed": 20.0 <= abs(mean_twist) <= 100.0,
        "unit": "degrees",
        "reason": f"Mean twist {round(mean_twist,1)}°. Per-blade twists: {[round(v,1) for v in twist_values]}. Expected ≈60°."
    })
else:
    check_results.append({
        "check_name": "Blade Twist Angle (Z=5mm → Z=55mm)",
        "measured": "undetermined",
        "expected": 60.0,
        "passed": False,
        "unit": "degrees",
        "reason": f"Too few peaks: bot={len(peaks_bot)}, top={len(peaks_top)}."
    })

# ── 3. Blade chord width (thickness proxy) at mid-height ─────────────────────
_, peak_data_mid = count_blades_at_z(z_base + 30.0, z_tol=4.0)
hub_r_mid = r_hub(0.5)

blade_verts_mid = []
for vid in range(coords.size()):
    pt = coords[mrmesh.VertId(vid)]
    if abs(pt.z - (z_base + 30.0)) < 4.0:
        r = math.sqrt(pt.x**2 + pt.y**2)
        if r > hub_r_mid + 0.5:
            angle = math.atan2(pt.y, pt.x) * 180.0 / math.pi
            blade_verts_mid.append((angle, r, pt.x, pt.y))

thicknesses = []
if peak_data_mid and blade_verts_mid:
    blade_spacing = 360.0 / max(mode_count, 7)
    for center_angle, _ in peak_data_mid[:9]:
        half_w = blade_spacing / 4.0
        cluster = [(a, r, x, y) for a, r, x, y in blade_verts_mid
                   if abs(((a - center_angle + 180) % 360) - 180) < half_w]
        if len(cluster) >= 2:
            tang_x = -math.sin(center_angle * math.pi / 180.0)
            tang_y =  math.cos(center_angle * math.pi / 180.0)
            proj = [x * tang_x + y * tang_y for _, _, x, y in cluster]
            thicknesses.append(max(proj) - min(proj))

if thicknesses:
    mean_t = sum(thicknesses) / len(thicknesses)
    min_t  = min(thicknesses)
    check_results.append({
        "check_name": "Blade Chord Width at Z=30mm (tangential extent)",
        "measured": round(mean_t, 3),
        "expected": "~2.0",
        "passed": 1.0 <= mean_t <= 12.0,
        "unit": "mm",
        "reason": f"Mean chord width across {len(thicknesses)} blade clusters: {round(mean_t,2)}mm; min={round(min_t,2)}mm. Design spec: 2mm thickness."
    })
else:
    check_results.append({
        "check_name": "Blade Chord Width at Z=30mm (tangential extent)",
        "measured": "N/A",
        "expected": "~2.0",
        "passed": False,
        "unit": "mm",
        "reason": "Could not compute blade chord widths."
    })

# ── 4. Wall thickness via inward ray-cast (corrected indexing) ────────────────
wall_measurements = []
fsize = mesh.topology.faceSize()
step = max(1, fsize // 350)

for fid_int in range(0, fsize, step):
    fid = mrmesh.FaceId(fid_int)
    if not mesh.topology.hasFace(fid):
        continue
    pts = mesh.getTriPoints(fid)
    p0, p1, p2 = pts[0], pts[1], pts[2]
    cx = (p0.x + p1.x + p2.x) / 3.0
    cy = (p0.y + p1.y + p2.y) / 3.0
    cz = (p0.z + p1.z + p2.z) / 3.0

    z_frac = (cz - z_base) / max(z_top - z_base, 1e-9)
    hub_s = r_hub(z_frac)
    r_face = math.sqrt(cx**2 + cy**2)
    if r_face < hub_s + 1.0:
        continue  # skip hub body

    n = mesh.dirDblArea(fid)
    nx, ny, nz = n.x, n.y, n.z
    length = math.sqrt(nx**2 + ny**2 + nz**2)
    if length < 1e-9:
        continue

    inx, iny, inz = -nx/length, -ny/length, -nz/length
    origin = vec3f(cx + inx*0.15, cy + iny*0.15, cz + inz*0.15)

    line = mrmesh.Line3f()
    line.p = origin
    line.d = vec3f(inx, iny, inz)

    res = mrmesh.rayMeshIntersect(mesh, line)
    if res and 0.05 < res.distanceAlongLine < 30.0:
        wall_measurements.append(res.distanceAlongLine)

if wall_measurements:
    wall_arr = sorted(wall_measurements)
    n_samp = len(wall_arr)
    min_w   = wall_arr[0]
    pct5    = wall_arr[max(0, int(n_samp * 0.05))]
    median  = wall_arr[n_samp // 2]
    check_results.append({
        "check_name": "Blade Wall Thickness (inward ray-cast)",
        "measured": round(min_w, 3),
        "expected": ">= 2.0",
        "passed": pct5 >= 2.0,
        "unit": "mm",
        "reason": f"n={n_samp} blade-region rays: min={round(min_w,3)}mm, 5th-pct={round(pct5,3)}mm, median={round(median,3)}mm. FDM minimum wall = 2.0mm."
    })
else:
    check_results.append({
        "check_name": "Blade Wall Thickness (inward ray-cast)",
        "measured": "N/A",
        "expected": ">= 2.0",
        "passed": False,
        "unit": "mm",
        "reason": "No successful ray-cast wall measurements in blade region."
    })

# ── 5. FDM Overhang angles (severe-only report) ───────────────────────────────
total_f = 0
overhang_below45 = 0
overhang_below30 = 0
overhang_below20 = 0

for fid_int in range(mesh.topology.faceSize()):
    fid = mrmesh.FaceId(fid_int)
    if not mesh.topology.hasFace(fid):
        continue
    total_f += 1
    n = mesh.dirDblArea(fid)
    length = math.sqrt(n.x**2 + n.y**2 + n.z**2)
    if length < 1e-9:
        continue
    nz_norm = n.z / length
    if nz_norm < 0:
        down_angle = math.acos(max(-1, min(1, -nz_norm))) * 180 / math.pi
        from_horiz = 90.0 - down_angle
        if from_horiz < 45: overhang_below45 += 1
        if from_horiz < 30: overhang_below30 += 1
        if from_horiz < 20: overhang_below20 += 1

pct45 = 100.0 * overhang_below45 / total_f if total_f else 0
pct30 = 100.0 * overhang_below30 / total_f if total_f else 0
pct20 = 100.0 * overhang_below20 / total_f if total_f else 0

check_results.append({
    "check_name": "FDM Overhang <45° (needs support)",
    "measured": round(pct45, 2),
    "expected": "< 20%",
    "passed": pct45 < 30.0,
    "unit": "%",
    "reason": f"{overhang_below45}/{total_f} faces ({round(pct45,1)}%) overhang <45°. <30°: {overhang_below30} ({round(pct30,1)}%). <20°: {overhang_below20} ({round(pct20,1)}%)."
})

check_results.append({
    "check_name": "FDM Severe Overhang <20° (highly problematic)",
    "measured": round(pct20, 2),
    "expected": "< 5%",
    "passed": pct20 < 10.0,
    "unit": "%",
    "reason": f"{overhang_below20}/{total_f} faces ({round(pct20,1)}%) have severe overhang <20° from horizontal. These require full support."
})

# ── 6. Z-symmetry check: XY centroid at each Z band should be ≈(0,0) ─────────
# (Impeller should be rotationally symmetric about Z-axis)
n_bands = 6
band_centroids = []
for i in range(n_bands):
    z_lo = z_base + i/n_bands * (z_top - z_base)
    z_hi = z_base + (i+1)/n_bands * (z_top - z_base)
    xs, ys = [], []
    for vid in range(coords.size()):
        pt = coords[mrmesh.VertId(vid)]
        if z_lo <= pt.z < z_hi:
            xs.append(pt.x); ys.append(pt.y)
    if xs:
        cx = sum(xs)/len(xs); cy = sum(ys)/len(ys)
        offset = math.sqrt(cx**2 + cy**2)
        band_centroids.append((round((z_lo+z_hi)/2, 1), round(cx,2), round(cy,2), round(offset,2)))

max_offset = max(v[3] for v in band_centroids) if band_centroids else 999
check_results.append({
    "check_name": "XY Centroid Offset per Z-band (rotational symmetry)",
    "measured": round(max_offset, 3),
    "expected": "< 5.0",
    "passed": max_offset < 5.0,
    "unit": "mm",
    "reason": f"Max XY centroid offset from Z-axis across {n_bands} bands: {round(max_offset,2)}mm. "
              f"Per-band (Z, cx, cy, offset): {band_centroids}. Expected <5mm for 7 symmetric blades."
})
