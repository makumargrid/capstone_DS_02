
import meshlib.mrmeshpy as mrmesh
import math

# ── helpers ──────────────────────────────────────────────────────────────────
def v3(x, y, z):
    v = mrmesh.Vector3f()
    v.x = x; v.y = y; v.z = z
    return v

# ── bounding box ─────────────────────────────────────────────────────────────
bb = mesh.getBoundingBox()
mn, mx_bb = bb.min, bb.max
cx = (mn.x + mx_bb.x) / 2.0
cy = (mn.y + mx_bb.y) / 2.0
cz_min = mn.z

verts = mesh.topology.getValidVerts()
points = mesh.points

# ═══════════════════════════════════════════════════════════════════
# CHECK 1 – Hub base diameter (design: 100 mm at Z=0)
# ═══════════════════════════════════════════════════════════════════
z_band_lo = cz_min
z_band_hi = cz_min + 3.0
radii_base = []
for vid in verts:
    p = points[vid]
    if z_band_lo <= p.z <= z_band_hi:
        r = math.sqrt((p.x - cx)**2 + (p.y - cy)**2)
        radii_base.append(r)

max_r_base = max(radii_base) if radii_base else 0.0
measured_base_diam = max_r_base * 2.0

# Also measure minimum radius at base (should be bore edge ~7.5 mm)
min_r_base = min(radii_base) if radii_base else 0.0

check_results.append({
    "check_name": "Hub Base Diameter (Z=0)",
    "measured": round(measured_base_diam, 3),
    "expected": 100.0,
    "passed": abs(measured_base_diam - 100.0) <= 5.0,
    "unit": "mm",
    "reason": f"Max radial extent at base Z-band [{z_band_lo:.1f},{z_band_hi:.1f}] = {measured_base_diam:.2f} mm (expected 100 mm ±5)"
})

# ═══════════════════════════════════════════════════════════════════
# CHECK 2 – Hub top diameter (design: 30 mm at Z=60)
# ═══════════════════════════════════════════════════════════════════
z_top_ref = cz_min + 60.0
z_top_lo  = z_top_ref - 3.0
z_top_hi  = z_top_ref + 3.0
radii_top = []
for vid in verts:
    p = points[vid]
    if z_top_lo <= p.z <= z_top_hi:
        r = math.sqrt((p.x - cx)**2 + (p.y - cy)**2)
        radii_top.append(r)

max_r_top = max(radii_top) if radii_top else 0.0
measured_top_diam = max_r_top * 2.0

check_results.append({
    "check_name": "Hub Top Diameter (Z=60)",
    "measured": round(measured_top_diam, 3),
    "expected": 30.0,
    "passed": abs(measured_top_diam - 30.0) <= 5.0,
    "unit": "mm",
    "reason": f"Max radial extent at top Z-band [{z_top_lo:.1f},{z_top_hi:.1f}] = {measured_top_diam:.2f} mm (expected 30 mm ±5)"
})

# ═══════════════════════════════════════════════════════════════════
# CHECK 3 – Total model height (design: 60 mm hub + blade extension)
# ═══════════════════════════════════════════════════════════════════
measured_total_height = mx_bb.z - mn.z
check_results.append({
    "check_name": "Total Model Height (Z extent)",
    "measured": round(measured_total_height, 3),
    "expected": 68.0,
    "passed": abs(measured_total_height - 68.0) <= 2.0,
    "unit": "mm",
    "reason": f"Mesh Z spans [{mn.z:.2f},{mx_bb.z:.2f}], height = {measured_total_height:.2f} mm. Hub cone = 60 mm; extra from blade tips expected."
})

# ═══════════════════════════════════════════════════════════════════
# CHECK 4 – Central bore diameter (design: 15 mm)
# Cast rays from near-axis outward at mid-height; first intersection = bore wall
# ═══════════════════════════════════════════════════════════════════
z_mid = cz_min + 30.0
bore_radii = []
num_rays = 36
for i in range(num_rays):
    angle = 2 * math.pi * i / num_rays
    dx, dy = math.cos(angle), math.sin(angle)
    # Fire from 1 mm off center outward
    inner_origin = v3(cx + 1.0 * dx, cy + 1.0 * dy, z_mid)
    inner_dir = v3(dx, dy, 0.0)
    inner_result = mrmesh.rayMeshIntersect(mesh, mrmesh.Line3f(inner_origin, inner_dir))
    if inner_result:
        hx = inner_result.proj.point.x
        hy = inner_result.proj.point.y
        r_bore = math.sqrt((hx - cx)**2 + (hy - cy)**2)
        bore_radii.append(r_bore)

if bore_radii:
    avg_bore_r = sum(bore_radii) / len(bore_radii)
    min_bore_r = min(bore_radii)
    max_bore_r = max(bore_radii)
    measured_bore_diam = avg_bore_r * 2.0
    bore_diam_str = f"avg={avg_bore_r*2:.2f}, min={min_bore_r*2:.2f}, max={max_bore_r*2:.2f} mm"
else:
    measured_bore_diam = 0.0
    bore_diam_str = "no hits"

check_results.append({
    "check_name": "Central Bore Diameter (Z-axis, 15 mm design)",
    "measured": round(measured_bore_diam, 3),
    "expected": 15.0,
    "passed": abs(measured_bore_diam - 15.0) <= 2.0,
    "unit": "mm",
    "reason": f"36 radial rays from near-axis at Z={z_mid:.0f} mm: {bore_diam_str} (expected 15 mm ±2)"
})

# ═══════════════════════════════════════════════════════════════════
# CHECK 5 – Blade count (design: 7 blades)
# Angular clustering of vertices beyond hub surface
# ═══════════════════════════════════════════════════════════════════
z_sample = cz_min + 20.0
frac_sample = 20.0 / 60.0
hub_r_at_sample = 50.0 - (50.0 - 15.0) * frac_sample  # ≈38.3 mm
blade_r_thresh = hub_r_at_sample + 3.0

blade_vertices_angles = []
for vid in verts:
    p = points[vid]
    if abs(p.z - z_sample) < 4.0:
        r = math.sqrt((p.x - cx)**2 + (p.y - cy)**2)
        if r > blade_r_thresh:
            angle_deg = math.degrees(math.atan2(p.y - cy, p.x - cx)) % 360
            blade_vertices_angles.append(angle_deg)

blade_vertices_angles.sort()
clusters = []
if blade_vertices_angles:
    current_cluster = [blade_vertices_angles[0]]
    gap_threshold = 15.0
    for a in blade_vertices_angles[1:]:
        if a - current_cluster[-1] > gap_threshold:
            clusters.append(current_cluster)
            current_cluster = [a]
        else:
            current_cluster.append(a)
    clusters.append(current_cluster)
    if len(clusters) > 1 and (360 - clusters[-1][-1] + clusters[0][0]) < gap_threshold:
        clusters[0] = clusters[-1] + clusters[0]
        clusters = clusters[:-1]

blade_count = len(clusters)

check_results.append({
    "check_name": "Number of Blades",
    "measured": blade_count,
    "expected": 7,
    "passed": blade_count == 7,
    "unit": "count",
    "reason": f"Angular clustering beyond hub radius at Z≈{z_sample:.0f} mm: {blade_count} clusters found (expected 7)"
})

# ═══════════════════════════════════════════════════════════════════
# CHECK 6 – Blade protrusion at base (design: 15 mm off hub at base)
# ═══════════════════════════════════════════════════════════════════
z_base_sample = cz_min + 2.0
hub_r_at_base = 50.0
radii_at_base_band = []
for vid in verts:
    p = points[vid]
    if abs(p.z - z_base_sample) < 3.0:
        r = math.sqrt((p.x - cx)**2 + (p.y - cy)**2)
        radii_at_base_band.append(r)

max_r_at_base_band = max(radii_at_base_band) if radii_at_base_band else 0.0
blade_protrusion_base = max_r_at_base_band - hub_r_at_base

check_results.append({
    "check_name": "Blade Protrusion at Base (design: 15 mm)",
    "measured": round(blade_protrusion_base, 3),
    "expected": 15.0,
    "passed": abs(blade_protrusion_base - 15.0) <= 5.0,
    "unit": "mm",
    "reason": f"Max radius at Z≈{z_base_sample:.0f} mm = {max_r_at_base_band:.2f} mm; hub base radius = {hub_r_at_base:.1f} mm → protrusion = {blade_protrusion_base:.2f} mm (expected 15 mm ±5)"
})

# ═══════════════════════════════════════════════════════════════════
# CHECK 7 – Blade protrusion at top (design: 5 mm off hub at top)
# ═══════════════════════════════════════════════════════════════════
z_top_sample = cz_min + 58.0
hub_r_at_top = 15.0
radii_at_top_band = []
for vid in verts:
    p = points[vid]
    if abs(p.z - z_top_sample) < 3.0:
        r = math.sqrt((p.x - cx)**2 + (p.y - cy)**2)
        radii_at_top_band.append(r)

max_r_at_top_band = max(radii_at_top_band) if radii_at_top_band else 0.0
blade_protrusion_top = max_r_at_top_band - hub_r_at_top

check_results.append({
    "check_name": "Blade Protrusion at Top (design: 5 mm)",
    "measured": round(blade_protrusion_top, 3),
    "expected": 5.0,
    "passed": abs(blade_protrusion_top - 5.0) <= 5.0,
    "unit": "mm",
    "reason": f"Max radius at Z≈{z_top_sample:.0f} mm = {max_r_at_top_band:.2f} mm; hub top radius = {hub_r_at_top:.1f} mm → protrusion = {blade_protrusion_top:.2f} mm (expected 5 mm ±5)"
})

# ═══════════════════════════════════════════════════════════════════
# CHECK 8 – Blade twist angle (design: ~60° around Z-axis)
# ═══════════════════════════════════════════════════════════════════
def get_blade_angle_centroids(z_target, z_band=5.0, r_extra=5.0):
    frac = max(0.0, min(1.0, (z_target - cz_min) / 60.0))
    hub_r = 50.0 - (50.0 - 15.0) * frac
    thresh = hub_r + r_extra
    blade_pts = []
    for vid in verts:
        p = points[vid]
        if abs(p.z - z_target) < z_band:
            r = math.sqrt((p.x - cx)**2 + (p.y - cy)**2)
            if r > thresh:
                angle_deg = math.degrees(math.atan2(p.y - cy, p.x - cx)) % 360
                blade_pts.append(angle_deg)
    blade_pts.sort()
    if not blade_pts:
        return []
    blade_clusters_loc = []
    cur = [blade_pts[0]]
    for a in blade_pts[1:]:
        if a - cur[-1] > 15.0:
            blade_clusters_loc.append(cur)
            cur = [a]
        else:
            cur.append(a)
    blade_clusters_loc.append(cur)
    if len(blade_clusters_loc) > 1 and (360 - blade_clusters_loc[-1][-1] + blade_clusters_loc[0][0]) < 15.0:
        blade_clusters_loc[0] = blade_clusters_loc[-1] + blade_clusters_loc[0]
        blade_clusters_loc = blade_clusters_loc[:-1]
    return [sum(c) / len(c) for c in blade_clusters_loc]

z_low  = cz_min + 5.0
z_high = cz_min + 55.0
centroids_low  = get_blade_angle_centroids(z_low)
centroids_high = get_blade_angle_centroids(z_high)

twist_note = f"low Z blades={len(centroids_low)}, high Z blades={len(centroids_high)}"
if centroids_low and centroids_high and len(centroids_low) == len(centroids_high):
    twist_angles = []
    for cl, ch in zip(centroids_low, centroids_high):
        diff = (ch - cl + 180) % 360 - 180
        twist_angles.append(abs(diff))
    avg_twist = sum(twist_angles) / len(twist_angles)
    twist_passed = 30.0 <= avg_twist <= 90.0
    twist_note += f"; avg twist = {avg_twist:.1f}°"
else:
    avg_twist = -1.0
    twist_passed = False

check_results.append({
    "check_name": "Blade Twist Angle Z-bottom to Z-top (design: ~60°)",
    "measured": round(avg_twist, 2) if avg_twist >= 0 else "N/A",
    "expected": 60.0,
    "passed": twist_passed,
    "unit": "degrees",
    "reason": twist_note + f" (expected ~60° ±30°)"
})

# ═══════════════════════════════════════════════════════════════════
# CHECK 9 – Bounding box X vs design brief (130 mm ±15)
# ═══════════════════════════════════════════════════════════════════
dim_x = mx_bb.x - mn.x
dim_y = mx_bb.y - mn.y
dim_z = mx_bb.z - mn.z

check_results.append({
    "check_name": "Bounding Box X (design: 130 mm ±15)",
    "measured": round(dim_x, 3),
    "expected": 130.0,
    "passed": abs(dim_x - 130.0) <= 15.0,
    "unit": "mm",
    "reason": f"Mesh X extent = {dim_x:.3f} mm (expected 130 ±15 mm)"
})

check_results.append({
    "check_name": "Bounding Box Y (design: 130 mm ±15)",
    "measured": round(dim_y, 3),
    "expected": 130.0,
    "passed": abs(dim_y - 130.0) <= 15.0,
    "unit": "mm",
    "reason": f"Mesh Y extent = {dim_y:.3f} mm (expected 130 ±15 mm)"
})

check_results.append({
    "check_name": "Bounding Box Z (design: 72 mm ±15)",
    "measured": round(dim_z, 3),
    "expected": 72.0,
    "passed": abs(dim_z - 72.0) <= 15.0,
    "unit": "mm",
    "reason": f"Mesh Z extent = {dim_z:.3f} mm (expected 72 ±15 mm)"
})
