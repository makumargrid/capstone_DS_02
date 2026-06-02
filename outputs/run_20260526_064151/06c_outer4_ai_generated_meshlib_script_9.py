
import meshlib.mrmeshpy as mrmesh
import math

# ── Setup ──────────────────────────────────────────────────────────────────────
bb = mesh.getBoundingBox()
min_pt = bb.min
max_pt = bb.max
dim_x = max_pt.x - min_pt.x
dim_y = max_pt.y - min_pt.y
dim_z = max_pt.z - min_pt.z

pts = mesh.points
topo = mesh.topology
vsize = topo.vertSize()
vec = pts.vec_

# ── 1. Z-HEIGHT ────────────────────────────────────────────────────────────────
check_results.append({
    "check_name": "Hub Z-height",
    "measured": round(dim_z, 4),
    "expected": 60.0,
    "passed": abs(dim_z - 60.0) <= 15.0,
    "unit": "mm",
    "reason": "Design specifies hub height of 60 mm (Z=0 to Z=60). Tolerance 15 mm per brief."
})

# ── 2. OVERALL X/Y EXTENTS ──────────────────────────────────────────────────────
check_results.append({
    "check_name": "Overall X-extent",
    "measured": round(dim_x, 4),
    "expected": 139.4,
    "passed": abs(dim_x - 139.4) <= 15.0,
    "unit": "mm",
    "reason": "Expected ~139.4 mm: base radius 50 + 15 mm blade protrusion = 65 mm radius = 130 mm diameter + blade thickness. Tolerance 15 mm."
})
check_results.append({
    "check_name": "Overall Y-extent",
    "measured": round(dim_y, 4),
    "expected": 139.4,
    "passed": abs(dim_y - 139.4) <= 15.0,
    "unit": "mm",
    "reason": "Same as X, expected ~139.4 mm. Tolerance 15 mm."
})

check_results.append({
    "check_name": "Mesh Z minimum (base at Z=0)",
    "measured": round(min_pt.z, 4),
    "expected": 0.0,
    "passed": abs(min_pt.z) <= 2.0,
    "unit": "mm",
    "reason": "Design places the hub base at Z=0."
})
check_results.append({
    "check_name": "Mesh Z maximum (top at Z=60)",
    "measured": round(max_pt.z, 4),
    "expected": 60.0,
    "passed": abs(max_pt.z - 60.0) <= 15.0,
    "unit": "mm",
    "reason": "Design places hub top at Z=60. Blades should not extend significantly above."
})

# ── 3. VERTEX RADIAL ANALYSIS ──────────────────────────────────────────────────
base_radii = []
top_radii = []
inner_radii = []
blade_verts_angles = []
base_blade_max_r = []
top_blade_max_r = []

for i in range(vsize):
    v = vec[i]
    x, y, z = v.x, v.y, v.z
    r = math.sqrt(x*x + y*y)

    if z <= 2.0:
        base_radii.append(r)
    if z >= dim_z - 2.0:
        top_radii.append(r)
    if r < 12.0:
        inner_radii.append(r)
    if r > 55.0:
        angle = math.degrees(math.atan2(y, x)) % 360.0
        blade_verts_angles.append(angle)
    if z <= 3.0 and r > 50.0:
        base_blade_max_r.append(r)
    if z >= dim_z - 3.0 and r > 15.0:
        top_blade_max_r.append(r)

max_base_radius = max(base_radii) if base_radii else 0.0
max_top_radius  = max(top_radii)  if top_radii  else 0.0

# ── 4. HUB BASE RADIUS ────────────────────────────────────────────────────────
check_results.append({
    "check_name": "Max radius at Z<=2 (hub base + blade protrusion, target ~65 mm)",
    "measured": round(max_base_radius, 4),
    "expected": 65.0,
    "passed": abs(max_base_radius - 65.0) <= 10.0,
    "unit": "mm",
    "reason": "Hub base radius 50 mm + 15 mm blade protrusion = 65 mm expected max at base."
})

# ── 5. CENTRAL BORE ────────────────────────────────────────────────────────────
if inner_radii:
    min_inner_r = min(inner_radii)
    max_inner_r = max(inner_radii)
    bore_diameter = max_inner_r * 2.0
    bore_present = min_inner_r < 9.0
else:
    min_inner_r = 999.0
    max_inner_r = 0.0
    bore_diameter = 0.0
    bore_present = False

check_results.append({
    "check_name": "Central bore present (vertices near axis)",
    "measured": bore_present,
    "expected": True,
    "passed": bore_present,
    "unit": "bool",
    "reason": "Design requires 15 mm diameter bore on Z axis. Checked for vertices at radius < 9 mm."
})
check_results.append({
    "check_name": "Central bore estimated diameter",
    "measured": round(bore_diameter, 4),
    "expected": 15.0,
    "passed": abs(bore_diameter - 15.0) <= 3.0,
    "unit": "mm",
    "reason": "Bore inner wall vertices found at radii " + str(round(min_inner_r,3)) + " to " + str(round(max_inner_r,3)) + " mm. Expected diameter 15 mm."
})

# Hole topology check
num_holes = topo.findNumHoles()
check_results.append({
    "check_name": "Through-bore topology: open hole boundaries",
    "measured": num_holes,
    "expected": 2,
    "passed": num_holes == 2,
    "unit": "count",
    "reason": "A through-bore creates 2 open boundary loops (top+bottom). Baseline reported hole_count=0 suggesting bore is capped/absent."
})

# ── 6. HUB TOP RADIUS ─────────────────────────────────────────────────────────
check_results.append({
    "check_name": "Max radius at Z>=58 (hub top + blade protrusion, target ~20 mm)",
    "measured": round(max_top_radius, 4),
    "expected": 20.0,
    "passed": abs(max_top_radius - 20.0) <= 8.0,
    "unit": "mm",
    "reason": "Hub top radius 15 mm + 5 mm blade protrusion at top = 20 mm expected. Tolerance 8 mm."
})

# ── 7. BLADE COUNTING ─────────────────────────────────────────────────────────
clusters = []
if blade_verts_angles:
    blade_verts_angles_sorted = sorted(blade_verts_angles)
    current_cluster = [blade_verts_angles_sorted[0]]
    for a in blade_verts_angles_sorted[1:]:
        if a - current_cluster[-1] < 18.0:
            current_cluster.append(a)
        else:
            clusters.append(current_cluster)
            current_cluster = [a]
    clusters.append(current_cluster)
    # Merge first and last if wrapping around 360
    if len(clusters) > 1:
        gap = 360.0 - clusters[-1][-1] + clusters[0][0]
        if gap < 18.0:
            clusters[0] = clusters[-1] + clusters[0]
            clusters.pop()

num_blade_clusters = len(clusters)
check_results.append({
    "check_name": "Number of blade clusters (target 7)",
    "measured": num_blade_clusters,
    "expected": 7,
    "passed": num_blade_clusters == 7,
    "unit": "count",
    "reason": "Design specifies 7 swept curved blades. Blades counted as angular clusters of vertices at r > 55 mm."
})

# ── 8. BLADE ANGULAR SPACING ─────────────────────────────────────────────────
if num_blade_clusters >= 2:
    cluster_centers = sorted([sum(c)/len(c) for c in clusters])
    spacings = [cluster_centers[i+1] - cluster_centers[i] for i in range(len(cluster_centers)-1)]
    spacings.append(360.0 - cluster_centers[-1] + cluster_centers[0])
    avg_spacing = sum(spacings) / len(spacings)
    expected_spacing = 360.0 / 7
    max_dev = max(abs(s - expected_spacing) for s in spacings)
    check_results.append({
        "check_name": "Blade angular spacing (target ~51.4 deg for 7 blades)",
        "measured": round(avg_spacing, 2),
        "expected": round(expected_spacing, 2),
        "passed": max_dev <= 10.0,
        "unit": "degrees",
        "reason": "7 blades evenly spaced at ~51.4 deg. Max deviation: " + str(round(max_dev, 2)) + " deg."
    })
else:
    check_results.append({
        "check_name": "Blade angular spacing (target ~51.4 deg for 7 blades)",
        "measured": "N/A",
        "expected": 51.43,
        "passed": False,
        "unit": "degrees",
        "reason": "Cannot compute - insufficient blade clusters detected."
    })

# ── 9. BLADE TWIST ANGLE ──────────────────────────────────────────────────────
base_blade_cluster_angles = {}
top_blade_cluster_angles  = {}
if clusters:
    cluster_ctr = [sum(c)/len(c) for c in clusters]
    for i in range(vsize):
        v = vec[i]
        x, y, z = v.x, v.y, v.z
        r = math.sqrt(x*x + y*y)
        if r < 55.0:
            continue
        angle = math.degrees(math.atan2(y, x)) % 360.0
        # Find nearest cluster
        nearest = min(range(len(cluster_ctr)), key=lambda ci: min(abs(cluster_ctr[ci] - angle), 360.0 - abs(cluster_ctr[ci] - angle)))
        if z <= 5.0:
            base_blade_cluster_angles.setdefault(nearest, []).append(angle)
        if z >= dim_z - 5.0:
            top_blade_cluster_angles.setdefault(nearest, []).append(angle)

twists = []
for idx in base_blade_cluster_angles:
    if idx in top_blade_cluster_angles:
        base_mean = sum(base_blade_cluster_angles[idx]) / len(base_blade_cluster_angles[idx])
        top_mean  = sum(top_blade_cluster_angles[idx])  / len(top_blade_cluster_angles[idx])
        twist = (top_mean - base_mean + 360.0) % 360.0
        if twist > 180.0:
            twist -= 360.0
        twists.append(abs(twist))

if twists:
    avg_twist = sum(twists) / len(twists)
    check_results.append({
        "check_name": "Blade twist angle bottom to top (target ~60 deg)",
        "measured": round(avg_twist, 2),
        "expected": 60.0,
        "passed": abs(avg_twist - 60.0) <= 20.0,
        "unit": "degrees",
        "reason": "Design specifies ~60 deg twist per blade from base to top. Measured from " + str(len(twists)) + " blade cluster(s)."
    })
else:
    check_results.append({
        "check_name": "Blade twist angle bottom to top (target ~60 deg)",
        "measured": "N/A",
        "expected": 60.0,
        "passed": False,
        "unit": "degrees",
        "reason": "Insufficient vertex coverage at both blade base and top zones to compute twist."
    })

# ── 10. BLADE BASE PROTRUSION ─────────────────────────────────────────────────
if base_blade_max_r:
    max_r_base = max(base_blade_max_r)
    protrusion_base = max_r_base - 50.0
    check_results.append({
        "check_name": "Blade protrusion at base (target 15 mm beyond hub r=50)",
        "measured": round(protrusion_base, 4),
        "expected": 15.0,
        "passed": abs(protrusion_base - 15.0) <= 5.0,
        "unit": "mm",
        "reason": "Max vertex radius at Z<=3: " + str(round(max_r_base, 3)) + " mm. Hub base r=50. Protrusion = " + str(round(protrusion_base, 3)) + " mm."
    })
else:
    check_results.append({
        "check_name": "Blade protrusion at base (target 15 mm beyond hub r=50)",
        "measured": "N/A",
        "expected": 15.0,
        "passed": False,
        "unit": "mm",
        "reason": "No vertices found at r > 50 mm within Z <= 3 mm."
    })

# ── 11. BLADE TOP PROTRUSION ──────────────────────────────────────────────────
if top_blade_max_r:
    max_r_top = max(top_blade_max_r)
    protrusion_top = max_r_top - 15.0
    check_results.append({
        "check_name": "Blade protrusion at top (target 5 mm beyond hub r=15)",
        "measured": round(protrusion_top, 4),
        "expected": 5.0,
        "passed": abs(protrusion_top - 5.0) <= 3.0,
        "unit": "mm",
        "reason": "Max vertex radius at Z >= " + str(round(dim_z-3, 1)) + ": " + str(round(max_r_top, 3)) + " mm. Hub top r=15. Protrusion = " + str(round(protrusion_top, 3)) + " mm."
    })
else:
    check_results.append({
        "check_name": "Blade protrusion at top (target 5 mm beyond hub r=15)",
        "measured": "N/A",
        "expected": 5.0,
        "passed": False,
        "unit": "mm",
        "reason": "No vertices found at r > 15 mm within Z >= " + str(round(dim_z-3, 1)) + " mm."
    })

# ── 12. WALL THICKNESS via ray casting ───────────────────────────────────────
# Cast radially outward from near Z-axis at mid-height to probe bore wall
thickness_samples = []
min_thickness = 1e9

for i in range(36):
    ang = 2 * math.pi * i / 36
    # Start from inside bore (r=5 mm), cast outward
    ox = 5.0 * math.cos(ang)
    oy = 5.0 * math.sin(ang)
    
    origin = mrmesh.Vector3f()
    origin.x = ox
    origin.y = oy
    origin.z = 30.0

    direction = mrmesh.Vector3f()
    direction.x = math.cos(ang)
    direction.y = math.sin(ang)
    direction.z = 0.0

    line = mrmesh.Line3f()
    line.p = origin
    line.d = direction

    result = mrmesh.rayMeshIntersect(mesh, line)
    if result:
        hit = result.proj.point
        d = math.sqrt((hit.x - ox)**2 + (hit.y - oy)**2 + (hit.z - 30.0)**2)
        thickness_samples.append(d)
        if d < min_thickness:
            min_thickness = d

if thickness_samples:
    check_results.append({
        "check_name": "Min wall thickness radial at mid-height Z=30 (bore wall to cone surface)",
        "measured": round(min_thickness, 4),
        "expected": 2.0,
        "passed": min_thickness >= 2.0,
        "unit": "mm",
        "reason": "Radial rays from r=5 at Z=30 outward. Min distance to first mesh surface = " + str(round(min_thickness, 3)) + " mm. Required >= 2 mm."
    })
else:
    check_results.append({
        "check_name": "Min wall thickness radial at mid-height Z=30",
        "measured": "N/A",
        "expected": 2.0,
        "passed": False,
        "unit": "mm",
        "reason": "No ray intersections at bore wall at Z=30 - bore likely absent."
    })

# ── 13. BLADE THICKNESS via tangential ray casting ────────────────────────────
blade_thickness_samples = []
if clusters:
    for cl in clusters[:min(5, len(clusters))]:
        cl_center_ang = math.radians(sum(cl) / len(cl))
        # Probe at r=62, Z=10, cast radially inward through blade
        r_start = 70.0
        ox2 = r_start * math.cos(cl_center_ang)
        oy2 = r_start * math.sin(cl_center_ang)

        origin2 = mrmesh.Vector3f()
        origin2.x = ox2
        origin2.y = oy2
        origin2.z = 10.0

        direction2 = mrmesh.Vector3f()
        direction2.x = -math.cos(cl_center_ang)
        direction2.y = -math.sin(cl_center_ang)
        direction2.z = 0.0

        line2 = mrmesh.Line3f()
        line2.p = origin2
        line2.d = direction2

        r2 = mrmesh.rayMeshIntersect(mesh, line2)
        if r2:
            h1x = r2.proj.point.x
            h1y = r2.proj.point.y
            h1z = r2.proj.point.z
            d1_along = r2.distanceAlongLine
            # Second ray from just past h1
            origin3 = mrmesh.Vector3f()
            origin3.x = h1x - 0.3 * math.cos(cl_center_ang)
            origin3.y = h1y - 0.3 * math.sin(cl_center_ang)
            origin3.z = 10.0

            line3 = mrmesh.Line3f()
            line3.p = origin3
            line3.d = direction2

            r3 = mrmesh.rayMeshIntersect(mesh, line3)
            if r3:
                h2x = r3.proj.point.x
                h2y = r3.proj.point.y
                bt = math.sqrt((h2x-h1x)**2 + (h2y-h1y)**2) + 0.3
                blade_thickness_samples.append(bt)

if blade_thickness_samples:
    avg_bt = sum(blade_thickness_samples) / len(blade_thickness_samples)
    check_results.append({
        "check_name": "Blade thickness measured via radial ray (target 2 mm)",
        "measured": round(avg_bt, 4),
        "expected": 2.0,
        "passed": abs(avg_bt - 2.0) <= 1.5,
        "unit": "mm",
        "reason": "Inward radial ray through blade at Z=10. Avg blade thickness from " + str(len(blade_thickness_samples)) + " samples = " + str(round(avg_bt, 3)) + " mm."
    })
else:
    check_results.append({
        "check_name": "Blade thickness measured via radial ray (target 2 mm)",
        "measured": "N/A",
        "expected": 2.0,
        "passed": False,
        "unit": "mm",
        "reason": "Could not measure blade thickness. Radial rays did not produce double-hit at blade location."
    })
