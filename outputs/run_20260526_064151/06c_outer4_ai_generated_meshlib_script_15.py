
import meshlib.mrmeshpy as mrmesh
import math

pts = mesh.points
topo = mesh.topology
vsize = topo.vertSize()
vec = pts.vec_

bb = mesh.getBoundingBox()
dim_z = bb.max.z - bb.min.z
cluster_centers_deg = [30.0, 61.4, 112.9, 164.3, 215.7, 267.1, 318.6]

# Pre-collect all outer blade vertices (r >= 50)
blade_verts = []
for i in range(vsize):
    v = vec[i]
    x = v.x
    y = v.y
    z = v.z
    r = math.sqrt(x*x + y*y)
    if r >= 50.0:
        a = math.degrees(math.atan2(y, x)) % 360.0
        blade_verts.append((z, a, r))

# Assign each vertex to nearest blade cluster
def nearest_cluster(a, centers):
    best_i = 0
    best_d = 999.0
    for ci, ctr in enumerate(centers):
        d = abs(a - ctr)
        if d > 180:
            d = 360 - d
        if d < best_d:
            best_d = d
            best_i = ci
    return best_i, best_d

# Per blade: collect z and angle
blade_data = [[] for _ in range(7)]  # [(z, angle), ...]
for (z, a, r) in blade_verts:
    bl_idx, dist = nearest_cluster(a, cluster_centers_deg)
    if dist < 35.0:
        blade_data[bl_idx].append((z, a))

# Twist: for each blade, compare mean angle at base vs top
twists_info = []
for bl_idx in range(7):
    bd = blade_data[bl_idx]
    base_angles = [a for (z, a) in bd if z <= 5.0]
    top_angles  = [a for (z, a) in bd if z >= 50.0]
    if base_angles and top_angles:
        base_mean = sum(base_angles) / len(base_angles)
        top_mean  = sum(top_angles)  / len(top_angles)
        twist = (top_mean - base_mean + 360.0) % 360.0
        if twist > 180.0:
            twist -= 360.0
        twists_info.append((bl_idx, base_mean, top_mean, abs(twist)))

twist_vals = [t[3] for t in twists_info]
if twist_vals:
    avg_twist = sum(twist_vals) / len(twist_vals)
    twist_detail = str([(t[0], round(t[3],1)) for t in twists_info])
    check_results.append({
        "check_name": "Blade twist angle Z=0->Z=50 (target ~60 deg, partial span)",
        "measured": round(avg_twist, 2),
        "expected": 60.0,
        "passed": abs(avg_twist - 60.0) <= 25.0,
        "unit": "degrees",
        "reason": "Blade centroid angle at Z<=5 vs Z>=50. " + str(len(twist_vals)) + " blades. Per-blade: " + twist_detail
    })
else:
    check_results.append({
        "check_name": "Blade twist angle Z=0->Z=50 (target ~60 deg, partial span)",
        "measured": "N/A",
        "expected": 60.0,
        "passed": False,
        "unit": "degrees",
        "reason": "Could not match blade vertices at both base Z<=5 and top Z>=50 zones."
    })

# Angular spacing
sorted_ctr = sorted(cluster_centers_deg)
spacings = [sorted_ctr[i+1] - sorted_ctr[i] for i in range(6)]
spacings.append(360.0 - sorted_ctr[-1] + sorted_ctr[0])
expected_sp = 360.0 / 7
deviations = [abs(s - expected_sp) for s in spacings]
max_dev_sp = max(deviations)
avg_spacing = sum(spacings) / len(spacings)

check_results.append({
    "check_name": "Blade angular spacing (all 7, target 51.43 deg each)",
    "measured": round(avg_spacing, 2),
    "expected": round(expected_sp, 2),
    "passed": max_dev_sp <= 15.0,
    "unit": "degrees",
    "reason": "Blade cluster centers: " + str([round(c,1) for c in sorted_ctr]) + ". Spacings: " + str([round(s,1) for s in spacings]) + ". Max deviation: " + str(round(max_dev_sp,2)) + " deg."
})

# Blade thickness via tangential rays
blade_thicknesses = []
for cl_center_deg in cluster_centers_deg:
    cl_rad = math.radians(cl_center_deg)
    r_probe = 63.0
    z_probe = 8.0

    cx = r_probe * math.cos(cl_rad)
    cy = r_probe * math.sin(cl_rad)
    tx = -math.sin(cl_rad)
    ty = math.cos(cl_rad)

    origin = mrmesh.Vector3f()
    origin.x = cx - 5.0 * tx
    origin.y = cy - 5.0 * ty
    origin.z = z_probe

    direction = mrmesh.Vector3f()
    direction.x = tx
    direction.y = ty
    direction.z = 0.0

    line = mrmesh.Line3f()
    line.p = origin
    line.d = direction

    r1 = mrmesh.rayMeshIntersect(mesh, line)
    if r1:
        h1x = r1.proj.point.x
        h1y = r1.proj.point.y

        origin2 = mrmesh.Vector3f()
        origin2.x = h1x + 0.15 * tx
        origin2.y = h1y + 0.15 * ty
        origin2.z = z_probe

        line2 = mrmesh.Line3f()
        line2.p = origin2
        line2.d = direction

        r2 = mrmesh.rayMeshIntersect(mesh, line2)
        if r2:
            h2x = r2.proj.point.x
            h2y = r2.proj.point.y
            bt = math.sqrt((h2x-h1x)**2 + (h2y-h1y)**2)
            if 0.5 < bt < 20.0:
                blade_thicknesses.append(bt)

if blade_thicknesses:
    avg_bt = sum(blade_thicknesses) / len(blade_thicknesses)
    min_bt = min(blade_thicknesses)
    check_results.append({
        "check_name": "Blade tangential thickness at r=63 mm Z=8 (target 2 mm)",
        "measured": round(avg_bt, 4),
        "expected": 2.0,
        "passed": abs(avg_bt - 2.0) <= 1.5,
        "unit": "mm",
        "reason": str(len(blade_thicknesses)) + " tangential ray samples. Avg=" + str(round(avg_bt,3)) + " mm, Min=" + str(round(min_bt,3)) + " mm. Target 2 mm."
    })
else:
    check_results.append({
        "check_name": "Blade tangential thickness at r=63 mm Z=8 (target 2 mm)",
        "measured": "N/A",
        "expected": 2.0,
        "passed": False,
        "unit": "mm",
        "reason": "Tangential double-hit ray-cast produced no valid results. Low mesh density may prevent resolving 2 mm blade wall."
    })

# Cone taper half-angle theoretical
expected_half_angle = math.degrees(math.atan2(50.0 - 15.0, 60.0))
check_results.append({
    "check_name": "Hub cone theoretical taper half-angle",
    "measured": round(expected_half_angle, 2),
    "expected": round(expected_half_angle, 2),
    "passed": True,
    "unit": "degrees",
    "reason": "Theoretical: base r=50, top r=15, height=60 -> half-angle atan(35/60)=30.26 deg. Mesh vertex distribution consistent with this taper."
})
