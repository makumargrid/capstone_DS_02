
import meshlib.mrmeshpy as mrmesh
import math

pts = mesh.points
topo = mesh.topology
vsize = topo.vertSize()
vec = pts.vec_

bb = mesh.getBoundingBox()
dim_z = bb.max.z - bb.min.z

# clusters from prev run
cluster_centers_deg = [30.0, 61.4, 112.9, 164.3, 215.7, 267.1, 318.6]

# Blade twist via nested loop - test this part
height_bands = [(0, 5), (10, 15), (20, 25), (30, 35), (40, 45), (50, 55), (55, 60)]

# Collect angle per blade per height band
blade_height_angles = []  # list of (blade_idx, z_mid, angle)

for bl_idx in range(len(cluster_centers_deg)):
    cl_ctr = cluster_centers_deg[bl_idx]
    for (zlo, zhi) in height_bands:
        band_angles = []
        for i in range(vsize):
            v = vec[i]
            x = v.x
            y = v.y
            z = v.z
            if z < zlo or z > zhi:
                continue
            r = math.sqrt(x*x + y*y)
            if r < 55.0:
                continue
            a = math.degrees(math.atan2(y, x)) % 360.0
            diff = abs(a - cl_ctr)
            if diff > 180:
                diff = 360 - diff
            if diff < 30.0:
                band_angles.append(a)
        if band_angles:
            z_mid = (zlo + zhi) / 2.0
            a_mean = sum(band_angles) / len(band_angles)
            blade_height_angles.append((bl_idx, z_mid, a_mean))

check_results.append({
    "check_name": "blade_height_angles_count",
    "measured": len(blade_height_angles),
    "expected": ">=7",
    "passed": len(blade_height_angles) >= 7,
    "unit": "count",
    "reason": "blade_height_angles entries: " + str(blade_height_angles[:5])
})
