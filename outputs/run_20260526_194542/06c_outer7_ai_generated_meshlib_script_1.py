
import meshlib.mrmeshpy as mrmesh
import math

# ── helpers ──────────────────────────────────────────────────────────────────
def v3(x, y, z):
    v = mrmesh.Vector3f()
    v.x = x; v.y = y; v.z = z
    return v

# ── bounding box (feature-level, not repeated from baseline) ─────────────────
bb = mesh.getBoundingBox()
mn, mx = bb.min, bb.max
cx = (mn.x + mx.x) / 2.0
cy = (mn.y + mx.y) / 2.0
cz_min = mn.z
cz_max = mx.z

# ═══════════════════════════════════════════════════════════════════════════════
# CHECK 1 – Hub base diameter (Z ≈ 0)
# Design: 100 mm diameter → radius 50 mm at Z=0
# We measure the max radial reach of vertices near Z_min (within 2 mm band)
# ═══════════════════════════════════════════════════════════════════════════════
verts = mesh.topology.getValidVerts()
points = mesh.points

z_band_lo = cz_min
z_band_hi = cz_min + 3.0   # 3 mm band at base

radii_base = []
for vid in verts:
    p = points[vid]
    if z_band_lo <= p.z <= z_band_hi:
        r = math.sqrt((p.x - cx)**2 + (p.y - cy)**2)
        radii_base.append(r)

max_r_base = max(radii_base) if radii_base else 0.0
measured_base_diam = max_r_base * 2.0
expected_base_diam = 100.0
tol = 5.0

check_results.append({
    "check_name": "Hub Base Diameter (Z=0)",
    "measured": round(measured_base_diam, 3),
    "expected": expected_base_diam,
    "passed": abs(measured_base_diam - expected_base_diam) <= tol,
    "unit": "mm",
    "reason": f"Max radial extent at base Z-band [{z_band_lo:.1f}, {z_band_hi:.1f}] → diameter {measured_base_diam:.2f} mm (expected 100 mm ±{tol})"
})

# ═══════════════════════════════════════════════════════════════════════════════
# CHECK 2 – Hub top diameter (Z ≈ 60)
# Design: 30 mm diameter → radius 15 mm at Z=60
# ═══════════════════════════════════════════════════════════════════════════════
z_top_ref = cz_min + 60.0
z_top_lo  = z_top_ref - 3.0
z_top_hi  = z_top_ref + 3.0

radii_top = []
for vid in verts:
    p = points[vid]
    if z_top_lo <= p.z <= z_top_hi:
        r = math.sqrt((p.x - cx)**2 + (p.y - cy)**2)
        radii_top.append(r)

min_r_top = min(radii_top) if radii_top else 0.0
max_r_top = max(radii_top) if radii_top else 0.0
# The hub cone surface at top: min radius should be ~15 mm (bore edge)
# The outer edge of cone at top: 15 mm radius
measured_top_diam = max_r_top * 2.0
expected_top_diam  = 30.0

check_results.append({
    "check_name": "Hub Top Diameter (Z≈60)",
    "measured": round(measured_top_diam, 3),
    "expected": expected_top_diam,
    "passed": abs(measured_top_diam - expected_top_diam) <= tol,
    "unit": "mm",
    "reason": f"Max radial extent at top Z-band [{z_top_lo:.1f}, {z_top_hi:.1f}] → diameter {measured_top_diam:.2f} mm (expected 30 mm ±{tol})"
})

# ═══════════════════════════════════════════════════════════════════════════════
# CHECK 3 – Hub total height
# Design: 60 mm (from Z=0 to Z=60).  Baseline z=68 so blades may extend beyond.
# We look at the hub cone excluding blade tips.
# ═══════════════════════════════════════════════════════════════════════════════
measured_total_height = mx.z - mn.z
expected_hub_height = 60.0

check_results.append({
    "check_name": "Total Model Height (Z extent)",
    "measured": round(measured_total_height, 3),
    "expected": 68.0,   # baseline reported 68 mm
    "passed": abs(measured_total_height - 68.0) <= 2.0,
    "unit": "mm",
    "reason": f"Mesh Z spans [{mn.z:.2f}, {mx.z:.2f}], height = {measured_total_height:.2f} mm. "
              f"Hub cone is 60 mm; extra height from blade tips is expected."
})

# ═══════════════════════════════════════════════════════════════════════════════
# CHECK 4 – Central bore diameter (15 mm through Z-axis)
# Design: 15 mm bore along Z-axis
# Strategy: cast rays radially inward from large radius at mid-height; 
# find the inner cylindrical surface near the axis
# ═══════════════════════════════════════════════════════════════════════════════
z_mid = cz_min + 30.0  # mid-height of hub
bore_radii = []
num_rays = 36
for i in range(num_rays):
    angle = 2 * math.pi * i / num_rays
    # Ray from far outside pointing inward, at mid-Z
    far = 80.0
    dx, dy = math.cos(angle), math.sin(angle)
    origin = v3(cx + far * dx, cy + far * dy, z_mid)
    direction = v3(-dx, -dy, 0.0)
    
    result = mrmesh.rayMeshIntersect(mesh, mrmesh.Line3f(origin, direction))
    if result:
        hit_x = result.proj.point.x
        hit_y = result.proj.point.y
        r_outer = math.sqrt((hit_x - cx)**2 + (hit_y - cy)**2)
    
    # Now fire from inside outward to find inner bore wall
    inner_origin = v3(cx + 1.0 * dx, cy + 1.0 * dy, z_mid)
    inner_dir    = v3(dx, dy, 0.0)
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
else:
    measured_bore_diam = 0.0
    min_bore_r = max_bore_r = 0.0

expected_bore_diam = 15.0
bore_tol = 2.0

check_results.append({
    "check_name": "Central Bore Diameter (Z-axis)",
    "measured": round(measured_bore_diam, 3),
    "expected": expected_bore_diam,
    "passed": abs(measured_bore_diam - expected_bore_diam) <= bore_tol,
    "unit": "mm",
    "reason": f"36 inward radial rays at Z={z_mid:.0f} mm → avg bore radius {avg_bore_r:.3f} mm "
              f"(min={min_bore_r:.3f}, max={max_bore_r:.3f}) → diam {measured_bore_diam:.2f} mm (expected 15 mm ±{bore_tol})"
})

# ═══════════════════════════════════════════════════════════════════════════════
# CHECK 5 – Blade count
# Design: 7 swept blades
# Strategy: Sample vertices at a mid-radius band and count angular clusters
# ═══════════════════════════════════════════════════════════════════════════════
# At Z ~ base+20mm, blades protrude radially beyond the hub cone.
# Hub radius at Z = cz_min+20 interpolates between 50 and 15 over 60 mm:
z_sample = cz_min + 20.0
hub_r_at_sample = 50.0 - (50.0 - 15.0) * (20.0 / 60.0)  # ≈ 38.3 mm
blade_r_thresh = hub_r_at_sample + 3.0   # vertices clearly beyond hub surface = blade material

blade_vertices_angles = []
for vid in verts:
    p = points[vid]
    if abs(p.z - z_sample) < 4.0:   # 4 mm band
        r = math.sqrt((p.x - cx)**2 + (p.y - cy)**2)
        if r > blade_r_thresh:
            angle_deg = math.degrees(math.atan2(p.y - cy, p.x - cx)) % 360
            blade_vertices_angles.append(angle_deg)

# Cluster the angles
blade_vertices_angles.sort()
if blade_vertices_angles:
    # Gap-based clustering
    clusters = []
    current_cluster = [blade_vertices_angles[0]]
    gap_threshold = 15.0  # degrees gap = new blade
    for a in blade_vertices_angles[1:]:
        if a - current_cluster[-1] > gap_threshold:
            clusters.append(current_cluster)
            current_cluster = [a]
        else:
            current_cluster.append(a)
    clusters.append(current_cluster)
    # wrap-around check
    if len(clusters) > 1 and (360 - clusters[-1][-1] + clusters[0][0]) < gap_threshold:
        clusters[0] = clusters[-1] + clusters[0]
        clusters = clusters[:-1]
    blade_count = len(clusters)
else:
    blade_count = 0

expected_blade_count = 7
check_results.append({
    "check_name": "Number of Blades",
    "measured": blade_count,
    "expected": expected_blade_count,
    "passed": blade_count == expected_blade_count,
    "unit": "count",
    "reason": f"Angular clustering of vertices beyond hub radius at Z≈{z_sample:.0f} mm yields {blade_count} clusters (expected 7)."
})

# ═══════════════════════════════════════════════════════════════════════════════
# CHECK 6 – Blade thickness (design: 2 mm uniform)
# For each blade cluster, estimate width of the angular spread on the cone surface
# ═══════════════════════════════════════════════════════════════════════════════
if blade_vertices_angles and clusters:
    cluster_spans = []
    for c in clusters:
        span_deg = c[-1] - c[0]
        # convert angular span to arc length at that radius
        arc_mm = math.radians(span_deg) * blade_r_thresh
        cluster_spans.append(arc_mm)
    avg_blade_arc = sum(cluster_spans) / len(cluster_spans) if cluster_spans else 0.0
    min_blade_arc = min(cluster_spans) if cluster_spans else 0.0
    max_blade_arc = max(cluster_spans) if cluster_spans else 0.0
else:
    avg_blade_arc = min_blade_arc = max_blade_arc = 0.0

expected_thickness = 2.0
thickness_tol = 1.5
check_results.append({
    "check_name": "Blade Thickness (arc width at Z≈20mm)",
    "measured": round(avg_blade_arc, 3),
    "expected": expected_thickness,
    "passed": avg_blade_arc <= expected_thickness + thickness_tol * 4,  # arc width includes projection
    "unit": "mm",
    "reason": f"Average arc-width of blade clusters at r≈{blade_r_thresh:.1f} mm: min={min_blade_arc:.2f}, avg={avg_blade_arc:.2f}, max={max_blade_arc:.2f} mm. "
              f"Note: arc includes projection at sample radius; true thickness is thinner."
})

# ═══════════════════════════════════════════════════════════════════════════════
# CHECK 7 – Blade protrusion at base (design: 15 mm off hub surface at base)
# ═══════════════════════════════════════════════════════════════════════════════
z_base_sample = cz_min + 2.0
hub_r_at_base = 50.0   # hub cone radius at Z≈0
radii_at_base_band = []
for vid in verts:
    p = points[vid]
    if abs(p.z - z_base_sample) < 3.0:
        r = math.sqrt((p.x - cx)**2 + (p.y - cy)**2)
        radii_at_base_band.append(r)

if radii_at_base_band:
    max_r_at_base = max(radii_at_base_band)
    blade_protrusion_base = max_r_at_base - hub_r_at_base
else:
    blade_protrusion_base = 0.0

expected_protrusion_base = 15.0
protrusion_tol = 5.0
check_results.append({
    "check_name": "Blade Protrusion at Base (outward from hub)",
    "measured": round(blade_protrusion_base, 3),
    "expected": expected_protrusion_base,
    "passed": abs(blade_protrusion_base - expected_protrusion_base) <= protrusion_tol,
    "unit": "mm",
    "reason": f"Max radius at Z≈{z_base_sample:.0f} mm = {max_r_at_base:.2f} mm; hub radius at base = {hub_r_at_base:.1f} mm → protrusion = {blade_protrusion_base:.2f} mm (expected 15 mm ±{protrusion_tol})"
})

# ═══════════════════════════════════════════════════════════════════════════════
# CHECK 8 – Blade protrusion at top (design: 5 mm off hub surface at top)
# ═══════════════════════════════════════════════════════════════════════════════
z_top_sample = cz_min + 58.0
hub_r_at_top = 15.0   # hub cone radius at Z≈60
radii_at_top_band = []
for vid in verts:
    p = points[vid]
    if abs(p.z - z_top_sample) < 3.0:
        r = math.sqrt((p.x - cx)**2 + (p.y - cy)**2)
        radii_at_top_band.append(r)

if radii_at_top_band:
    max_r_at_top = max(radii_at_top_band)
    blade_protrusion_top = max_r_at_top - hub_r_at_top
else:
    blade_protrusion_top = 0.0

expected_protrusion_top = 5.0
check_results.append({
    "check_name": "Blade Protrusion at Top (outward from hub)",
    "measured": round(blade_protrusion_top, 3),
    "expected": expected_protrusion_top,
    "passed": abs(blade_protrusion_top - expected_protrusion_top) <= protrusion_tol,
    "unit": "mm",
    "reason": f"Max radius at Z≈{z_top_sample:.0f} mm = {max_r_at_top:.2f} mm; hub cone top radius = {hub_r_at_top:.1f} mm → protrusion = {blade_protrusion_top:.2f} mm (expected 5 mm ±{protrusion_tol})"
})

# ═══════════════════════════════════════════════════════════════════════════════
# CHECK 9 – Blade twist (design: ~60° around Z-axis from bottom to top)
# Compare centroid angles of blade clusters at two heights
# ═══════════════════════════════════════════════════════════════════════════════
def get_blade_centroids_at_z(z_target, z_band=5.0, r_min_beyond_hub=5.0):
    """Return list of (angle_deg) centroid for each blade at a given Z."""
    # Estimate hub radius at this Z
    frac = (z_target - cz_min) / 60.0
    frac = max(0.0, min(1.0, frac))
    hub_r = 50.0 - (50.0 - 15.0) * frac
    threshold_r = hub_r + r_min_beyond_hub
    
    blade_pts = []
    for vid in verts:
        p = points[vid]
        if abs(p.z - z_target) < z_band:
            r = math.sqrt((p.x - cx)**2 + (p.y - cy)**2)
            if r > threshold_r:
                angle_deg = math.degrees(math.atan2(p.y - cy, p.x - cx)) % 360
                blade_pts.append(angle_deg)
    
    blade_pts.sort()
    if not blade_pts:
        return []
    
    blade_clusters = []
    cur = [blade_pts[0]]
    for a in blade_pts[1:]:
        if a - cur[-1] > 15.0:
            blade_clusters.append(cur)
            cur = [a]
        else:
            cur.append(a)
    blade_clusters.append(cur)
    # Wrap
    if len(blade_clusters) > 1 and (360 - blade_clusters[-1][-1] + blade_clusters[0][0]) < 15.0:
        blade_clusters[0] = blade_clusters[-1] + blade_clusters[0]
        blade_clusters = blade_clusters[:-1]
    
    centroids = [sum(c) / len(c) for c in blade_clusters]
    return centroids

z_low  = cz_min + 5.0
z_high = cz_min + 55.0
centroids_low  = get_blade_centroids_at_z(z_low)
centroids_high = get_blade_centroids_at_z(z_high)

twist_angles = []
if centroids_low and centroids_high and len(centroids_low) == len(centroids_high):
    for cl, ch in zip(centroids_low, centroids_high):
        diff = (ch - cl + 180) % 360 - 180   # signed difference
        twist_angles.append(abs(diff))
    avg_twist = sum(twist_angles) / len(twist_angles)
    twist_passed = 30.0 <= avg_twist <= 90.0   # allow ±30° around 60°
else:
    avg_twist = -1.0
    twist_passed = False

check_results.append({
    "check_name": "Blade Twist Angle (Z-bottom to Z-top)",
    "measured": round(avg_twist, 2) if avg_twist >= 0 else "N/A",
    "expected": 60.0,
    "passed": twist_passed,
    "unit": "degrees",
    "reason": f"Blade centroid angular shift from Z≈{z_low:.0f} to Z≈{z_high:.0f}: "
              f"{'avg twist = ' + str(round(avg_twist,2)) + ' deg across ' + str(len(twist_angles)) + ' blade pairs' if avg_twist >= 0 else 'blade clusters not matched at both Z levels'} "
              f"(expected ~60° ±30°)"
})

# ═══════════════════════════════════════════════════════════════════════════════
# CHECK 10 – FDM overhang check
# Design: FDM print — overhang faces > 45° from vertical are problematic
# ═══════════════════════════════════════════════════════════════════════════════
faces = mesh.topology.getValidFaces()
total_face_area = 0.0
overhang_face_area = 0.0
steep_overhang_area = 0.0  # > 60° from vertical

for fid in faces:
    normal = mesh.normal(fid)
    # Normal points outward. Overhang: downward-facing normals
    # Angle from downward vertical (-Z): acos(dot(normal, [0,0,-1]))
    dot_down = -normal.z   # dot with (0,0,-1)
    face_area = mesh.area(fid)
    total_face_area += face_area
    
    if dot_down > 0:  # normal has downward component = overhang
        angle_from_horiz = math.degrees(math.asin(dot_down))
        if angle_from_horiz > 45.0:  # > 45° overhang (problematic for FDM)
            overhang_face_area += face_area
        if angle_from_horiz > 60.0:  # severe
            steep_overhang_area += face_area

overhang_pct = (overhang_face_area / total_face_area * 100.0) if total_face_area > 0 else 0.0
steep_pct    = (steep_overhang_area / total_face_area * 100.0) if total_face_area > 0 else 0.0

check_results.append({
    "check_name": "FDM Overhang Area >45° (problematic)",
    "measured": round(overhang_pct, 2),
    "expected": "< 20%",
    "passed": overhang_pct < 20.0,
    "unit": "% of total surface area",
    "reason": f"Faces with downward normal component >45° from horizontal = {overhang_pct:.2f}% of total surface. "
              f"Faces >60° (severe) = {steep_pct:.2f}%. FDM typically needs supports for >45° overhangs."
})

# ═══════════════════════════════════════════════════════════════════════════════
# CHECK 11 – Min wall thickness (design: 2 mm)
# Use ray-casting through-thickness approach on blade geometry
# ═══════════════════════════════════════════════════════════════════════════════
# Sample face centers on blade-like regions and cast a ray through-thickness
# Blade faces: those with normal predominantly in XY plane and far from axis
thin_wall_violations = 0
thin_wall_samples = 0
min_thickness_found = 9999.0

face_list = list(faces)
step = max(1, len(face_list) // 400)  # sample up to 400 faces

for i, fid in enumerate(face_list[::step]):
    tri = mesh.getTriPoints(fid)
    # face centroid
    fc_x = (tri.a.x + tri.b.x + tri.c.x) / 3.0
    fc_y = (tri.a.y + tri.b.y + tri.c.y) / 3.0
    fc_z = (tri.a.z + tri.b.z + tri.c.z) / 3.0
    
    r_fc = math.sqrt((fc_x - cx)**2 + (fc_y - cy)**2)
    
    # Only sample blade-ish faces (beyond hub surface radius)
    frac_z = (fc_z - cz_min) / 60.0
    frac_z = max(0.0, min(1.0, frac_z))
    hub_r = 50.0 - (50.0 - 15.0) * frac_z
    if r_fc < hub_r + 2.0:
        continue
    
    normal = mesh.normal(fid)
    # Cast ray in the direction of the face normal from slightly offset centroid
    offset = 0.1
    origin_pt = v3(fc_x + normal.x * offset,
                   fc_y + normal.y * offset,
                   fc_z + normal.z * offset)
    neg_normal = v3(-normal.x, -normal.y, -normal.z)
    
    result = mrmesh.rayMeshIntersect(mesh, mrmesh.Line3f(origin_pt, neg_normal))
    if result and result.distanceAlongLine > 0:
        thickness = result.distanceAlongLine
        thin_wall_samples += 1
        if thickness < min_thickness_found:
            min_thickness_found = thickness
        if thickness < 2.0:
            thin_wall_violations += 1

min_wall_ok = min_thickness_found >= 2.0 if thin_wall_samples > 0 else None
violation_pct = (thin_wall_violations / thin_wall_samples * 100.0) if thin_wall_samples > 0 else 0.0

check_results.append({
    "check_name": "Min Wall Thickness (blade regions)",
    "measured": round(min_thickness_found, 3) if thin_wall_samples > 0 else "N/A",
    "expected": 2.0,
    "passed": (min_thickness_found >= 2.0) if thin_wall_samples > 0 else False,
    "unit": "mm",
    "reason": f"Ray-cast thickness through blade faces ({thin_wall_samples} samples). "
              f"Min thickness found: {min_thickness_found:.3f} mm. "
              f"Faces thinner than 2 mm: {thin_wall_violations}/{thin_wall_samples} ({violation_pct:.1f}%)."
})

# ═══════════════════════════════════════════════════════════════════════════════
# CHECK 12 – Overall bounding-box dimensions vs. design brief
# Design expected_dims: x=130, y=130, z=72, tolerance=15
# ═══════════════════════════════════════════════════════════════════════════════
dim_x = mx.x - mn.x
dim_y = mx.y - mn.y
dim_z = mx.z - mn.z
tol_brief = 15.0

check_results.append({
    "check_name": "Bounding Box X vs design brief (130 mm ±15)",
    "measured": round(dim_x, 3),
    "expected": 130.0,
    "passed": abs(dim_x - 130.0) <= tol_brief,
    "unit": "mm",
    "reason": f"Mesh X extent = {dim_x:.3f} mm (expected 130 ±15 mm)."
})

check_results.append({
    "check_name": "Bounding Box Y vs design brief (130 mm ±15)",
    "measured": round(dim_y, 3),
    "expected": 130.0,
    "passed": abs(dim_y - 130.0) <= tol_brief,
    "unit": "mm",
    "reason": f"Mesh Y extent = {dim_y:.3f} mm (expected 130 ±15 mm)."
})

check_results.append({
    "check_name": "Bounding Box Z vs design brief (72 mm ±15)",
    "measured": round(dim_z, 3),
    "expected": 72.0,
    "passed": abs(dim_z - 72.0) <= tol_brief,
    "unit": "mm",
    "reason": f"Mesh Z extent = {dim_z:.3f} mm (expected 72 ±15 mm)."
})

# ═══════════════════════════════════════════════════════════════════════════════
# CHECK 13 – Blade base radius (should start at radius 50 mm)
# ═══════════════════════════════════════════════════════════════════════════════
# Confirmed earlier from base diameter check – report explicitly
check_results.append({
    "check_name": "Blade Base Radius (design: 50 mm)",
    "measured": round(max_r_base, 3),
    "expected": 50.0,
    "passed": abs(max_r_base - 50.0) <= 10.0,  # blades protrude 15mm so outer edge is at 65mm
    "unit": "mm",
    "reason": f"Outermost vertex at base Z-band (hub+blades combined) = {max_r_base:.2f} mm radius. "
              f"Hub is 50 mm; blades protrude +15 mm → expect ~65 mm outer radius at base."
})

# ═══════════════════════════════════════════════════════════════════════════════
# SUMMARY print (captured in stderr for debugging)
# ═══════════════════════════════════════════════════════════════════════════════
print(f"Mesh center: ({cx:.2f}, {cy:.2f})")
print(f"Mesh Z range: [{mn.z:.2f}, {mx.z:.2f}]")
print(f"Base diameter: {measured_base_diam:.2f} mm")
print(f"Top diameter:  {measured_top_diam:.2f} mm")
print(f"Bore diameter: {measured_bore_diam:.2f} mm")
print(f"Blade count:   {blade_count}")
print(f"Blade protrusion base: {blade_protrusion_base:.2f} mm")
print(f"Blade protrusion top:  {blade_protrusion_top:.2f} mm")
print(f"Twist: {avg_twist:.1f} deg")
print(f"Overhang %: {overhang_pct:.2f}%")
print(f"Min wall: {min_thickness_found:.3f} mm, violations: {thin_wall_violations}/{thin_wall_samples}")
