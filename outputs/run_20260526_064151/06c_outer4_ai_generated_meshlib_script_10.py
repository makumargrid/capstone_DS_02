
import meshlib.mrmeshpy as mrmesh
import math

# Better blade thickness: cast tangentially (perpendicular to radial) through a blade
pts = mesh.points
topo = mesh.topology
vsize = topo.vertSize()
vec = pts.vec_

bb = mesh.getBoundingBox()
dim_z = bb.max.z - bb.min.z

# First reconstruct blade clusters
blade_verts_angles = []
for i in range(vsize):
    v = vec[i]
    x, y, z = v.x, v.y, v.z
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

print("Num clusters:", len(clusters))
cluster_centers_deg = [sum(c)/len(c) for c in clusters]
print("Cluster centers (deg):", [round(cc,1) for cc in cluster_centers_deg])

# Blade thickness: cast TANGENTIALLY through a blade at r=62 Z=10
# Tangential direction = perpendicular to radial direction in XY plane
blade_thicknesses = []
for cl_center_deg in cluster_centers_deg[:5]:
    cl_rad = math.radians(cl_center_deg)
    r_probe = 62.0  # radial position through blade
    z_probe = 10.0

    # Blade center position
    cx = r_probe * math.cos(cl_rad)
    cy = r_probe * math.sin(cl_rad)

    # Tangential direction (perpendicular to radial)
    tx = -math.sin(cl_rad)
    ty =  math.cos(cl_rad)

    # Start from -tangential side (offset by 5 mm to be outside blade)
    start_x = cx - 5.0 * tx
    start_y = cy - 5.0 * ty

    origin = mrmesh.Vector3f()
    origin.x = start_x
    origin.y = start_y
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
        d1 = r1.distanceAlongLine
        print(f"  Cluster {round(cl_center_deg,1)}: first hit at dist={d1:.3f}, pt=({h1x:.2f},{h1y:.2f})")

        # Second ray starting past first hit
        origin2 = mrmesh.Vector3f()
        origin2.x = h1x + 0.2 * tx
        origin2.y = h1y + 0.2 * ty
        origin2.z = z_probe

        line2 = mrmesh.Line3f()
        line2.p = origin2
        line2.d = direction

        r2 = mrmesh.rayMeshIntersect(mesh, line2)
        if r2:
            h2x = r2.proj.point.x
            h2y = r2.proj.point.y
            d2 = r2.distanceAlongLine
            bt = math.sqrt((h2x-h1x)**2 + (h2y-h1y)**2)
            print(f"    second hit dist={d2:.3f}, blade thickness={bt:.3f} mm")
            if bt < 15.0:  # realistic blade thickness (not passing through whole hub)
                blade_thicknesses.append(bt)
        else:
            print("    no second hit")
    else:
        print(f"  Cluster {round(cl_center_deg,1)}: no first hit")

if blade_thicknesses:
    avg_bt = sum(blade_thicknesses) / len(blade_thicknesses)
    min_bt = min(blade_thicknesses)
    print(f"\nBlade thicknesses: {[round(b,3) for b in blade_thicknesses]}")
    print(f"Avg: {avg_bt:.3f}, Min: {min_bt:.3f}")
    check_results.append({
        "check_name": "Blade thickness at mid-span r=62 (target 2 mm)",
        "measured": round(avg_bt, 4),
        "expected": 2.0,
        "passed": abs(avg_bt - 2.0) <= 1.5,
        "unit": "mm",
        "reason": "Tangential ray-cast through blade cross-section at r=62 mm, Z=10 mm. Measured " + str(len(blade_thicknesses)) + " samples."
    })
else:
    check_results.append({
        "check_name": "Blade thickness at mid-span r=62 (target 2 mm)",
        "measured": "N/A",
        "expected": 2.0,
        "passed": False,
        "unit": "mm",
        "reason": "Tangential ray-cast produced no valid double-hit through blade."
    })

# Improved blade twist: use the actual cluster vertex data
# Separate blade verts by height bands and measure angular position
# Use the twisted geometry: at base blades have one angle, at top they are rotated

# Collect per-blade per-height band: use r > 58 mm (outer edge of blades) at different Z levels
# to track the leading edge of each blade
height_bands = [(0, 5), (10, 15), (20, 25), (30, 35), (40, 45), (50, 55), (55, 60)]
blade_angle_by_height = {}  # blade_idx -> list of (z_mean, angle_mean)

for bl_idx, cl_center_deg in enumerate(cluster_centers_deg):
    band_data = []
    for (zlo, zhi) in height_bands:
        band_angles = []
        for i in range(vsize):
            v = vec[i]
            x, y, z = v.x, v.y, v.z
            if not (zlo <= z <= zhi):
                continue
            r = math.sqrt(x*x + y*y)
            if r < 55.0:
                continue
            a = math.degrees(math.atan2(y, x)) % 360.0
            # Check if this vertex belongs to this blade cluster (within 25 deg)
            diff = abs(a - cl_center_deg)
            if diff > 180:
                diff = 360 - diff
            if diff < 30.0:
                band_angles.append(a)
        if band_angles:
            z_mean = (zlo + zhi) / 2.0
            a_mean = sum(band_angles) / len(band_angles)
            band_data.append((z_mean, a_mean))
    blade_angle_by_height[bl_idx] = band_data

print("\nBlade twist analysis:")
twists_per_blade = []
for bl_idx, band_data in blade_angle_by_height.items():
    if len(band_data) >= 2:
        base_a = band_data[0][1]   # angle at lowest height band
        top_a  = band_data[-1][1]  # angle at highest height band
        twist = (top_a - base_a + 360.0) % 360.0
        if twist > 180.0:
            twist -= 360.0
        print(f"  Blade {bl_idx}: base_angle={base_a:.1f} deg at Z={band_data[0][0]}, top_angle={top_a:.1f} deg at Z={band_data[-1][0]}, twist={twist:.1f} deg")
        twists_per_blade.append(abs(twist))

if twists_per_blade:
    avg_twist = sum(twists_per_blade) / len(twists_per_blade)
    check_results.append({
        "check_name": "Blade twist angle bottom to top (target ~60 deg)",
        "measured": round(avg_twist, 2),
        "expected": 60.0,
        "passed": abs(avg_twist - 60.0) <= 20.0,
        "unit": "degrees",
        "reason": "Measured blade centroid angle shift from Z=2.5 band to Z=57.5 band for " + str(len(twists_per_blade)) + " blades. Target 60 deg."
    })
else:
    check_results.append({
        "check_name": "Blade twist angle bottom to top (target ~60 deg)",
        "measured": "N/A",
        "expected": 60.0,
        "passed": False,
        "unit": "mm",
        "reason": "Could not measure twist - insufficient vertex coverage across height bands."
    })

# Angular spacing analysis
if len(cluster_centers_deg) == 7:
    sorted_ctr = sorted(cluster_centers_deg)
    spacings = [sorted_ctr[i+1] - sorted_ctr[i] for i in range(6)]
    spacings.append(360.0 - sorted_ctr[-1] + sorted_ctr[0])
    expected = 360.0 / 7
    max_dev = max(abs(s - expected) for s in spacings)
    print("\nBlade spacings:", [round(s,1) for s in spacings])
    print("Max deviation from 51.43:", round(max_dev, 2))
    check_results.append({
        "check_name": "Blade angular spacing uniformity (max deviation from 51.4 deg)",
        "measured": round(max_dev, 2),
        "expected": 0.0,
        "passed": max_dev <= 15.0,
        "unit": "degrees",
        "reason": "Max deviation from ideal 51.43 deg spacing. All spacings: " + str([round(s,1) for s in spacings])
    })
