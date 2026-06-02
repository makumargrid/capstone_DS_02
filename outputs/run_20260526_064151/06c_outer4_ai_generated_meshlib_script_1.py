
import meshlib.mrmeshpy as mrmesh
import math

check_results = []

# ── 1. BOUNDING BOX / Z-HEIGHT ──────────────────────────────────────────────
bb = mesh.getBoundingBox()
min_pt = bb.min
max_pt = bb.max

dim_x = max_pt.x - min_pt.x
dim_y = max_pt.y - min_pt.y
dim_z = max_pt.z - min_pt.z

# Z height: hub is 60 mm tall; blades may add a small amount, but spec says hub height = 60 mm
check_results.append({
    "check_name": "Hub Z-height (z_mm)",
    "measured": round(dim_z, 4),
    "expected": 60.0,
    "passed": abs(dim_z - 60.0) <= 15.0,
    "unit": "mm",
    "reason": "Design specifies hub height of 60 mm (Z=0 to Z=60). Tolerance ±15 mm per brief."
})

# X / Y overall diameter footprint  (expected ~139.4 mm from brief)
check_results.append({
    "check_name": "Overall X-extent",
    "measured": round(dim_x, 4),
    "expected": 139.4,
    "passed": abs(dim_x - 139.4) <= 15.0,
    "unit": "mm",
    "reason": "Expected ~139.4 mm based on blade protrusion at base (base radius 50 mm + 15 mm blade protrusion = 65 mm → 130 mm + blade width). Tolerance ±15 mm."
})
check_results.append({
    "check_name": "Overall Y-extent",
    "measured": round(dim_y, 4),
    "expected": 139.4,
    "passed": abs(dim_y - 139.4) <= 15.0,
    "unit": "mm",
    "reason": "Expected ~139.4 mm same as X. Tolerance ±15 mm."
})

# ── 2. HUB BASE DIAMETER (at Z=0) ────────────────────────────────────────────
# Sample all vertices near Z ≈ 0 and find max radial extent → base diameter
verts = mesh.points
topo = mesh.topology
valid_verts = topo.getValidVerts()

base_radii = []
top_radii  = []
all_z_vals = []

num_verts = topo.vertSize()
for vi in range(num_verts):
    vid = mrmesh.VertId(vi)
    if not valid_verts.test(vid):
        continue
    v = verts[vid]
    all_z_vals.append(v.z)
    r = math.sqrt(v.x**2 + v.y**2)
    if v.z <= 2.0:        # near base
        base_radii.append(r)
    if v.z >= dim_z - 2.0:   # near top
        top_radii.append(r)

max_base_radius = max(base_radii) if base_radii else 0.0
max_top_radius  = max(top_radii) if top_radii else 0.0

check_results.append({
    "check_name": "Hub base max radius at Z≈0",
    "measured": round(max_base_radius, 4),
    "expected": 65.0,
    "passed": abs(max_base_radius - 65.0) <= 10.0,
    "unit": "mm",
    "reason": "Hub base radius 50 mm + max blade protrusion 15 mm = 65 mm expected at base."
})

# Pure hub cone base radius = 50 mm → check that majority of base verts are ≤ 50 mm + blade
pure_hub_base_verts = [r for r in base_radii if r <= 52.0]  # within 2 mm of cone edge
check_results.append({
    "check_name": "Hub cone base diameter (2×50 mm = 100 mm)",
    "measured": round(max_base_radius * 2, 4) if base_radii else 0.0,
    "expected": 100.0,
    "passed": True,   # informational — blades extend beyond
    "unit": "mm",
    "reason": "Informational: outer extent at base. Blades protrude 15 mm so full outer diameter exceeds 100 mm."
})

# ── 3. CENTRAL BORE HOLE DIAMETER (15 mm) ────────────────────────────────────
# The bore goes through Z axis. Look for vertices very close to the axis (small radius)
inner_radii = []
for vi in range(num_verts):
    vid = mrmesh.VertId(vi)
    if not valid_verts.test(vid):
        continue
    v = verts[vid]
    r = math.sqrt(v.x**2 + v.y**2)
    if r < 12.0:   # potential bore-wall verts (bore radius = 7.5 mm)
        inner_radii.append(r)

if inner_radii:
    min_inner_r = min(inner_radii)
    max_inner_r = max(inner_radii)
    estimated_bore_diameter = max_inner_r * 2.0
    bore_present = min_inner_r < 10.0
else:
    min_inner_r = 0.0
    max_inner_r = 0.0
    estimated_bore_diameter = 0.0
    bore_present = False

check_results.append({
    "check_name": "Central bore present",
    "measured": bore_present,
    "expected": True,
    "passed": bore_present,
    "unit": "bool",
    "reason": "Design specifies a 15 mm diameter bore along the Z axis. Checked for vertices at radius < 10 mm."
})

check_results.append({
    "check_name": "Central bore diameter (≈15 mm)",
    "measured": round(estimated_bore_diameter, 4),
    "expected": 15.0,
    "passed": abs(estimated_bore_diameter - 15.0) <= 3.0,
    "unit": "mm",
    "reason": f"Inner bore wall vertices found at radii {round(min_inner_r,3)}–{round(max_inner_r,3)} mm. Expected bore diameter = 15 mm (radius 7.5 mm)."
})

# Check if hole count is zero (baseline) – bore was reported as hole_count=0 meaning it's filled or capped
check_results.append({
    "check_name": "Bore through-hole topology (open boundary edges)",
    "measured": mesh.topology.findNumHoles(),
    "expected": 2,
    "passed": mesh.topology.findNumHoles() == 2,
    "unit": "count",
    "reason": "A through-bore should produce 2 open hole boundaries (top and bottom circles). Baseline reports hole_count=0 suggesting bore may be absent or capped."
})

# ── 4. HUB TOP DIAMETER (30 mm at Z=60) ──────────────────────────────────────
# At the top of the hub (Z ≈ 60), the cone top surface should have radius ≈ 15 mm (dia 30 mm)
# But blades at top may extend to 15+5=20 mm radius → up to 40 mm dia
top_pure_radii = [r for r in top_radii if r <= 22.0]
if top_pure_radii:
    max_top_pure = max(top_pure_radii)
else:
    max_top_pure = max_top_radius if top_radii else 0.0

check_results.append({
    "check_name": "Hub top outer radius at Z≈60 (hub surface + blade protrusion)",
    "measured": round(max_top_radius, 4),
    "expected": 20.0,
    "passed": abs(max_top_radius - 20.0) <= 8.0,
    "unit": "mm",
    "reason": "Hub top cone radius = 15 mm + blade protrusion 5 mm at top = 20 mm expected maximum radius at Z≈60."
})

# ── 5. NUMBER OF BLADES ───────────────────────────────────────────────────────
# Count distinct angular clusters of blade-protruding vertices
# Blade verts are those with radius > 52 mm (beyond pure hub surface)
blade_verts_angles = []
for vi in range(num_verts):
    vid = mrmesh.VertId(vi)
    if not valid_verts.test(vid):
        continue
    v = verts[vid]
    r = math.sqrt(v.x**2 + v.y**2)
    if r > 55.0:  # significantly beyond cone surface
        angle = math.degrees(math.atan2(v.y, v.x)) % 360.0
        blade_verts_angles.append(angle)

# Cluster blade angles into groups separated by at least 15 degrees
if blade_verts_angles:
    blade_verts_angles.sort()
    clusters = []
    current_cluster = [blade_verts_angles[0]]
    for a in blade_verts_angles[1:]:
        if a - current_cluster[-1] < 18.0:
            current_cluster.append(a)
        else:
            clusters.append(current_cluster)
            current_cluster = [a]
    clusters.append(current_cluster)
    # Merge first and last cluster if they wrap around 360/0
    if len(clusters) > 1 and (360.0 - clusters[-1][-1] + clusters[0][0]) < 18.0:
        clusters[0] = clusters[-1] + clusters[0]
        clusters.pop()
    num_blade_clusters = len(clusters)
else:
    num_blade_clusters = 0

check_results.append({
    "check_name": "Number of aerodynamic blades (counted via radial clusters)",
    "measured": num_blade_clusters,
    "expected": 7,
    "passed": num_blade_clusters == 7,
    "unit": "count",
    "reason": "Design specifies 7 swept curved blades. Blades counted as angular clusters of vertices extending > 55 mm from Z axis."
})

# ── 6. BLADE ANGULAR SPACING ─────────────────────────────────────────────────
if num_blade_clusters == 7:
    cluster_centers = [sum(c)/len(c) for c in clusters]
    cluster_centers.sort()
    spacings = []
    for i in range(1, len(cluster_centers)):
        spacings.append(cluster_centers[i] - cluster_centers[i-1])
    # wrap-around spacing
    spacings.append(360.0 - cluster_centers[-1] + cluster_centers[0])
    avg_spacing = sum(spacings) / len(spacings)
    expected_spacing = 360.0 / 7  # ≈ 51.43°
    max_deviation = max(abs(s - expected_spacing) for s in spacings)
    check_results.append({
        "check_name": "Blade angular spacing (should be ≈51.4° for 7 blades)",
        "measured": round(avg_spacing, 2),
        "expected": round(expected_spacing, 2),
        "passed": max_deviation <= 10.0,
        "unit": "degrees",
        "reason": f"7 blades should be evenly spaced at ~51.4°. Max deviation from expected: {round(max_deviation,2)}°."
    })
else:
    check_results.append({
        "check_name": "Blade angular spacing (should be ≈51.4° for 7 blades)",
        "measured": "N/A",
        "expected": 51.43,
        "passed": False,
        "unit": "degrees",
        "reason": f"Cannot compute spacing as blade count ({num_blade_clusters}) ≠ 7."
    })

# ── 7. BLADE TWIST (60° from bottom to top) ──────────────────────────────────
# For each angular cluster, find centroid angle at base (Z<5) vs top (Z>55)
base_blade_angles = {}
top_blade_angles  = {}

for vi in range(num_verts):
    vid = mrmesh.VertId(vi)
    if not valid_verts.test(vid):
        continue
    v = verts[vid]
    r = math.sqrt(v.x**2 + v.y**2)
    if r < 55.0:
        continue
    angle = math.degrees(math.atan2(v.y, v.x)) % 360.0
    # Assign to nearest cluster
    nearest = min(range(len(clusters)), key=lambda i: abs((sum(clusters[i])/len(clusters[i])) - angle) if clusters else 999)
    if v.z <= 5.0:
        base_blade_angles.setdefault(nearest, []).append(angle)
    if v.z >= dim_z - 5.0:
        top_blade_angles.setdefault(nearest, []).append(angle)

twists = []
for idx in base_blade_angles:
    if idx in top_blade_angles:
        base_mean = sum(base_blade_angles[idx]) / len(base_blade_angles[idx])
        top_mean  = sum(top_blade_angles[idx]) / len(top_blade_angles[idx])
        twist = (top_mean - base_mean + 360.0) % 360.0
        if twist > 180.0:
            twist -= 360.0
        twists.append(abs(twist))

if twists:
    avg_twist = sum(twists) / len(twists)
    check_results.append({
        "check_name": "Blade twist angle bottom→top (target ≈60°)",
        "measured": round(avg_twist, 2),
        "expected": 60.0,
        "passed": abs(avg_twist - 60.0) <= 20.0,
        "unit": "degrees",
        "reason": f"Design specifies ~60° twist from base to top per blade. Measured average twist from {len(twists)} blade(s)."
    })
else:
    check_results.append({
        "check_name": "Blade twist angle bottom→top (target ≈60°)",
        "measured": "N/A",
        "expected": 60.0,
        "passed": False,
        "unit": "degrees",
        "reason": "Insufficient vertex coverage at both blade base and top to compute twist."
    })

# ── 8. MINIMUM WALL THICKNESS (≥2 mm) ────────────────────────────────────────
# Ray-cast inward from face centers to measure local thickness
# Cast rays in -Z direction through hub flat areas (the thinnest wall is the bore wall)
# Simplified: measure through-casting at some sample points near the bore wall at mid-height

num_samples = 40
min_thickness_found = 1e9
thickness_samples = []

for i in range(num_samples):
    angle = 2 * math.pi * i / num_samples
    # At bore wall (r ≈ 7.5 mm) at mid-height Z ≈ 30 mm
    r_test = 7.5  # bore inner radius
    x_out = r_test * math.cos(angle)
    y_out = r_test * math.sin(angle)
    # Direction: radially outward from bore center
    dx = math.cos(angle)
    dy = math.sin(angle)

    # Origin: slightly inside the bore (r < 7.5)
    origin = mrmesh.Vector3f()
    origin.x = 6.0 * math.cos(angle)
    origin.y = 6.0 * math.sin(angle)
    origin.z = 30.0

    direction = mrmesh.Vector3f()
    direction.x = dx
    direction.y = dy
    direction.z = 0.0

    line = mrmesh.Line3f()
    line.p = origin
    line.d = direction

    result = mrmesh.rayMeshIntersect(mesh, line)
    if result:
        hit_pt = result.proj.point
        dist = math.sqrt((hit_pt.x - origin.x)**2 + (hit_pt.y - origin.y)**2 + (hit_pt.z - origin.z)**2)
        thickness_samples.append(dist)
        if dist < min_thickness_found:
            min_thickness_found = dist

if thickness_samples:
    avg_thickness = sum(thickness_samples) / len(thickness_samples)
    check_results.append({
        "check_name": "Min wall thickness (bore wall radial, mid-height)",
        "measured": round(min_thickness_found, 4),
        "expected": 2.0,
        "passed": min_thickness_found >= 2.0,
        "unit": "mm",
        "reason": f"Radial ray-cast from just inside bore at Z=30 in {num_samples} directions. Min measured wall thickness = {round(min_thickness_found,3)} mm. Required ≥ 2 mm."
    })
else:
    check_results.append({
        "check_name": "Min wall thickness (bore wall radial, mid-height)",
        "measured": "N/A",
        "expected": 2.0,
        "passed": False,
        "unit": "mm",
        "reason": "No ray intersections found at bore wall — bore may be absent or solid at centre."
    })

# ── 9. BLADE THICKNESS (~2 mm) ───────────────────────────────────────────────
# Ray-cast tangentially through a blade mid-span
# At base (Z≈0, r≈50), cast radially inward to measure blade encounter
blade_thicknesses = []
for cl_idx, cluster in enumerate(clusters[:min(3, len(clusters))]):
    cl_center_angle = math.radians(sum(cluster)/len(cluster))
    # position slightly above blade center at base
    r_probe = 60.0  # outside blade
    x_probe = r_probe * math.cos(cl_center_angle)
    y_probe = r_probe * math.sin(cl_center_angle)
    
    origin2 = mrmesh.Vector3f()
    origin2.x = x_probe
    origin2.y = y_probe
    origin2.z = 3.0

    direction2 = mrmesh.Vector3f()
    direction2.x = -math.cos(cl_center_angle)
    direction2.y = -math.sin(cl_center_angle)
    direction2.z = 0.0

    line2 = mrmesh.Line3f()
    line2.p = origin2
    line2.d = direction2

    result2 = mrmesh.rayMeshIntersect(mesh, line2)
    if result2:
        # First hit is outer blade surface
        h1 = result2.proj.point
        d1 = math.sqrt((h1.x - x_probe)**2 + (h1.y - y_probe)**2)
        # Continue casting from just past first hit to find second surface
        origin3 = mrmesh.Vector3f()
        origin3.x = h1.x - 0.5*math.cos(cl_center_angle)
        origin3.y = h1.y - 0.5*math.sin(cl_center_angle)
        origin3.z = 3.0

        line3 = mrmesh.Line3f()
        line3.p = origin3
        line3.d = direction2

        result3 = mrmesh.rayMeshIntersect(mesh, line3)
        if result3:
            h2 = result3.proj.point
            blade_t = math.sqrt((h2.x-h1.x)**2 + (h2.y-h1.y)**2 + (h2.z-h1.z)**2) + 0.5
            blade_thicknesses.append(blade_t)

if blade_thicknesses:
    avg_blade_thickness = sum(blade_thicknesses) / len(blade_thicknesses)
    check_results.append({
        "check_name": "Blade thickness at base (target 2 mm)",
        "measured": round(avg_blade_thickness, 4),
        "expected": 2.0,
        "passed": abs(avg_blade_thickness - 2.0) <= 1.5,
        "unit": "mm",
        "reason": f"Radial ray-cast through blade at base cross-section. Measured avg blade thickness from {len(blade_thicknesses)} sample(s)."
    })
else:
    check_results.append({
        "check_name": "Blade thickness at base (target 2 mm)",
        "measured": "N/A",
        "expected": 2.0,
        "passed": False,
        "unit": "mm",
        "reason": "Could not measure blade thickness — no double-hit ray intersections at blade location."
    })

# ── 10. BLADE BASE PROTRUSION (15 mm at base) ────────────────────────────────
# At Z≈0 blades should protrude ~15 mm above hub surface
# Hub surface at base: r=50 mm; so blade tips at base should reach r≈65 mm
base_blade_max_r = []
for vi in range(num_verts):
    vid = mrmesh.VertId(vi)
    if not valid_verts.test(vid):
        continue
    v = verts[vid]
    if v.z <= 3.0:
        r = math.sqrt(v.x**2 + v.y**2)
        if r > 50.0:
            base_blade_max_r.append(r)

if base_blade_max_r:
    max_blade_r_base = max(base_blade_max_r)
    blade_protrusion_base = max_blade_r_base - 50.0
    check_results.append({
        "check_name": "Blade protrusion at base (target 15 mm beyond hub r=50)",
        "measured": round(blade_protrusion_base, 4),
        "expected": 15.0,
        "passed": abs(blade_protrusion_base - 15.0) <= 5.0,
        "unit": "mm",
        "reason": f"Max vertex radius at Z≤3: {round(max_blade_r_base,3)} mm. Hub base radius = 50 mm. Protrusion = {round(blade_protrusion_base,3)} mm (expected 15 mm)."
    })
else:
    check_results.append({
        "check_name": "Blade protrusion at base (target 15 mm beyond hub r=50)",
        "measured": "N/A",
        "expected": 15.0,
        "passed": False,
        "unit": "mm",
        "reason": "No vertices found beyond r=50 mm at Z≤3."
    })

# ── 11. BLADE TOP PROTRUSION (5 mm at top) ────────────────────────────────────
top_blade_max_r = []
for vi in range(num_verts):
    vid = mrmesh.VertId(vi)
    if not valid_verts.test(vid):
        continue
    v = verts[vid]
    if v.z >= dim_z - 3.0:
        r = math.sqrt(v.x**2 + v.y**2)
        if r > 15.0:
            top_blade_max_r.append(r)

if top_blade_max_r:
    max_blade_r_top = max(top_blade_max_r)
    blade_protrusion_top = max_blade_r_top - 15.0
    check_results.append({
        "check_name": "Blade protrusion at top (target 5 mm beyond hub r=15)",
        "measured": round(blade_protrusion_top, 4),
        "expected": 5.0,
        "passed": abs(blade_protrusion_top - 5.0) <= 3.0,
        "unit": "mm",
        "reason": f"Max vertex radius at Z≥{round(dim_z-3,1)}: {round(max_blade_r_top,3)} mm. Hub top radius = 15 mm. Protrusion = {round(blade_protrusion_top,3)} mm (expected 5 mm)."
    })
else:
    check_results.append({
        "check_name": "Blade protrusion at top (target 5 mm beyond hub r=15)",
        "measured": "N/A",
        "expected": 5.0,
        "passed": False,
        "unit": "mm",
        "reason": "No vertices found beyond r=15 mm at Z near top."
    })

# ── 12. Z BASE LOCATION ───────────────────────────────────────────────────────
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

# ── Summary stats ─────────────────────────────────────────────────────────────
print(f"dim_x={dim_x:.3f}, dim_y={dim_y:.3f}, dim_z={dim_z:.3f}")
print(f"max_base_radius={max_base_radius:.3f}, max_top_radius={max_top_radius:.3f}")
print(f"inner_radii count={len(inner_radii)}, min={min_inner_r:.3f}, max={max_inner_r:.3f}")
print(f"blade clusters={num_blade_clusters}")
print(f"hole count={mesh.topology.findNumHoles()}")
print(f"thickness samples={len(thickness_samples)}, min={min_thickness_found:.3f}")
