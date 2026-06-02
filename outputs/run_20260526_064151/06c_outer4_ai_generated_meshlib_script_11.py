
import meshlib.mrmeshpy as mrmesh
import math

pts = mesh.points
topo = mesh.topology
vsize = topo.vertSize()
vec = pts.vec_

bb = mesh.getBoundingBox()
dim_z = bb.max.z - bb.min.z

# Test: reconstruct clusters
blade_verts_angles = []
for i in range(vsize):
    v = vec[i]
    x = v.x
    y = v.y
    z = v.z
    r = math.sqrt(x*x + y*y)
    if r > 55.0:
        angle = math.degrees(math.atan2(y, x)) % 360.0
        blade_verts_angles.append(angle)

clusters = []
if blade_verts_angles:
    bva_s = sorted(blade_verts_angles)
    cur = [bva_s[0]]
    for a in bva_s[1:]:
        if a - cur[-1] < 18.0:
            cur.append(a)
        else:
            clusters.append(cur)
            cur = [a]
    clusters.append(cur)
    if len(clusters) > 1:
        gap = 360.0 - clusters[-1][-1] + clusters[0][0]
        if gap < 18.0:
            clusters[0] = clusters[-1] + clusters[0]
            clusters.pop()

cluster_centers_deg = [sum(c)/len(c) for c in clusters]

check_results.append({
    "check_name": "cluster_rebuild",
    "measured": len(clusters),
    "expected": 7,
    "passed": len(clusters) == 7,
    "unit": "count",
    "reason": "Cluster rebuild: " + str(len(clusters)) + " clusters found, centers: " + str([round(cc,1) for cc in cluster_centers_deg])
})
