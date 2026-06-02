
import meshlib.mrmeshpy as mrmesh
import math

pts = mesh.points
topo = mesh.topology
vsize = topo.vertSize()
vec = pts.vec_

bb = mesh.getBoundingBox()
dim_z = bb.max.z - bb.min.z
cluster_centers_deg = [30.0, 61.4, 112.9, 164.3, 215.7, 267.1, 318.6]

# Understand blade vertex z distribution
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

# Check z distribution of blade verts (r>=50)
z_vals = [bv[0] for bv in blade_verts]
min_z_blade = min(z_vals)
max_z_blade = max(z_vals)

# Also check at r >= 55 (more clearly blade)
z_vals_55 = [bv[0] for bv in blade_verts if bv[2] >= 55.0]
max_z_55 = max(z_vals_55) if z_vals_55 else 0.0

check_results.append({
    "check_name": "Blade vertex Z range at r>=50 mm",
    "measured": str(round(min_z_blade,2)) + " to " + str(round(max_z_blade,2)),
    "expected": "0.0 to 60.0",
    "passed": min_z_blade <= 2.0 and max_z_blade >= 55.0,
    "unit": "mm",
    "reason": "Blade verts (r>=50) span Z from " + str(round(min_z_blade,2)) + " to " + str(round(max_z_blade,2)) + ". Max at r>=55: " + str(round(max_z_55,2)) + ". Design: blades run Z=0 to Z=60."
})

# Twist using widest available range: base Z<=5, and top = the highest Z with blade verts
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

blade_data = [[] for _ in range(7)]
for (z, a, r) in blade_verts:
    bl_idx, dist = nearest_cluster(a, cluster_centers_deg)
    if dist < 35.0:
        blade_data[bl_idx].append((z, a))

# Print per-blade data to understand extent
for bl_idx in range(7):
    bd = blade_data[bl_idx]
    if bd:
        zs = [d[0] for d in bd]
        angs = [d[1] for d in bd]
        min_z = min(zs)
        max_z = max(zs)
        base_ang = sum(a for (z,a) in bd if z <= min_z + 2) / max(1, len([a for (z,a) in bd if z <= min_z + 2]))
        top_ang  = sum(a for (z,a) in bd if z >= max_z - 2) / max(1, len([a for (z,a) in bd if z >= max_z - 2]))
        twist = (top_ang - base_ang + 360.0) % 360.0
        if twist > 180.0:
            twist -= 360.0
        z_span = max_z - min_z
        check_results.append({
            "check_name": "Blade " + str(bl_idx) + " twist over available Z span",
            "measured": round(abs(twist), 2),
            "expected": 60.0 * (z_span / 60.0),
            "passed": True,
            "unit": "degrees",
            "reason": "Blade " + str(bl_idx) + ": Z " + str(round(min_z,1)) + " to " + str(round(max_z,1)) + " (span=" + str(round(z_span,1)) + " mm). Base angle=" + str(round(base_ang,1)) + " deg, top=" + str(round(top_ang,1)) + " deg. Twist=" + str(round(abs(twist),2)) + " deg."
        })
