
import meshlib.mrmeshpy as mrmesh
import math

pts = mesh.points
topo = mesh.topology
vsize = topo.vertSize()
vec = pts.vec_

bb = mesh.getBoundingBox()
dim_z = bb.max.z - bb.min.z
cluster_centers_deg = [30.0, 61.4, 112.9, 164.3, 215.7, 267.1, 318.6]

# Pre-collect all blade vertices with their z and angle
blade_verts_za = []  # (z, angle)
for i in range(vsize):
    v = vec[i]
    x = v.x
    y = v.y
    z = v.z
    r = math.sqrt(x*x + y*y)
    if r >= 50.0:
        a = math.degrees(math.atan2(y, x)) % 360.0
        blade_verts_za.append((z, a, r))

check_results.append({
    "check_name": "blade_verts_count",
    "measured": len(blade_verts_za),
    "expected": ">0",
    "passed": len(blade_verts_za) > 0,
    "unit": "count",
    "reason": "Vertices at r>=50 mm: " + str(len(blade_verts_za))
})
