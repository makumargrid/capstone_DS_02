
import meshlib.mrmeshpy as mrmesh
import math

def v3(x, y, z):
    v = mrmesh.Vector3f()
    v.x = x; v.y = y; v.z = z
    return v

bb = mesh.getBoundingBox()
mn, mx_bb = bb.min, bb.max
cx = (mn.x + mx_bb.x) / 2.0
cy = (mn.y + mx_bb.y) / 2.0
cz_min = mn.z

faces = mesh.topology.getValidFaces()
face_list = list(faces)

# ═══════════════════════════════════════════════════════════════════
# CHECK A – FDM Overhang: faces with normal > 45° below horizontal
# ═══════════════════════════════════════════════════════════════════
total_face_area = 0.0
overhang_face_area = 0.0
steep_overhang_area = 0.0

for fid in face_list:
    normal = mesh.normal(fid)
    face_area = mesh.area(fid)
    total_face_area += face_area
    dot_down = -normal.z   # dot with (0,0,-1): positive = face is downward-facing
    if dot_down > 0:
        angle_from_horiz = math.degrees(math.asin(min(1.0, dot_down)))
        if angle_from_horiz > 45.0:
            overhang_face_area += face_area
        if angle_from_horiz > 60.0:
            steep_overhang_area += face_area

overhang_pct = (overhang_face_area / total_face_area * 100.0) if total_face_area > 0 else 0.0
steep_pct    = (steep_overhang_area / total_face_area * 100.0) if total_face_area > 0 else 0.0

check_results.append({
    "check_name": "FDM Overhang Area >45° from horizontal",
    "measured": round(overhang_pct, 2),
    "expected": "< 20%",
    "passed": overhang_pct < 20.0,
    "unit": "% of total surface",
    "reason": f"Faces with downward normal >45° from horiz = {overhang_pct:.2f}% of total surface area. Severe (>60°) = {steep_pct:.2f}%. FDM requires supports for >45° overhangs."
})

# ═══════════════════════════════════════════════════════════════════
# CHECK B – Min wall thickness via ray-casting (design: 2 mm)
# Use face centroid from vertex average via topology
# ═══════════════════════════════════════════════════════════════════
thin_wall_violations = 0
thin_wall_samples = 0
min_thickness_found = 9999.0
step = max(1, len(face_list) // 500)

for fid in face_list[::step]:
    # Get face centroid from edge-walk
    e = mesh.topology.edgeWithLeft(fid)
    v0 = mesh.topology.org(e)
    e2 = mesh.topology.next(e)
    v1 = mesh.topology.org(e2)
    e3 = mesh.topology.next(e2)
    v2 = mesh.topology.org(e3)

    p0 = mesh.points[v0]
    p1 = mesh.points[v1]
    p2 = mesh.points[v2]
    fc_x = (p0.x + p1.x + p2.x) / 3.0
    fc_y = (p0.y + p1.y + p2.y) / 3.0
    fc_z = (p0.z + p1.z + p2.z) / 3.0

    # Only check blade-ish geometry (outside hub radius)
    frac_z = max(0.0, min(1.0, (fc_z - cz_min) / 60.0))
    hub_r = 50.0 - (50.0 - 15.0) * frac_z
    r_fc = math.sqrt((fc_x - cx)**2 + (fc_y - cy)**2)
    if r_fc < hub_r + 1.5:
        continue

    normal = mesh.normal(fid)
    # Fire a ray inward through the wall (opposite to normal)
    offset = 0.05
    origin_pt = v3(fc_x + normal.x * offset,
                   fc_y + normal.y * offset,
                   fc_z + normal.z * offset)
    neg_normal = v3(-normal.x, -normal.y, -normal.z)

    result = mrmesh.rayMeshIntersect(mesh, mrmesh.Line3f(origin_pt, neg_normal))
    if result and result.distanceAlongLine > 0.01:
        thickness = result.distanceAlongLine
        thin_wall_samples += 1
        if thickness < min_thickness_found:
            min_thickness_found = thickness
        if thickness < 2.0:
            thin_wall_violations += 1

violation_pct = (thin_wall_violations / thin_wall_samples * 100.0) if thin_wall_samples > 0 else 0.0

check_results.append({
    "check_name": "Min Wall Thickness — blade regions (design: 2 mm)",
    "measured": round(min_thickness_found, 3) if thin_wall_samples > 0 else "N/A",
    "expected": 2.0,
    "passed": (min_thickness_found >= 2.0) if thin_wall_samples > 0 else False,
    "unit": "mm",
    "reason": f"Ray-cast through-thickness on {thin_wall_samples} blade-face samples. "
              f"Min thickness = {min_thickness_found:.3f} mm. "
              f"Sub-2 mm violations: {thin_wall_violations}/{thin_wall_samples} ({violation_pct:.1f}%)"
})

# ═══════════════════════════════════════════════════════════════════
# CHECK C – Bore present (hole_count from baseline = 0; check inner surface)
# Verify the bore is truly open by counting vertices near Z-axis center at both ends
# ═══════════════════════════════════════════════════════════════════
verts = mesh.topology.getValidVerts()
points = mesh.points

# Count vertices within 8 mm radius at Z≈bottom and Z≈top
bore_r_check = 8.0
bore_verts_bottom = sum(
    1 for vid in verts
    if abs(points[vid].z - cz_min) < 3.0
    and math.sqrt((points[vid].x - cx)**2 + (points[vid].y - cy)**2) < bore_r_check
)
bore_verts_top = sum(
    1 for vid in verts
    if abs(points[vid].z - (cz_min + 60.0)) < 3.0
    and math.sqrt((points[vid].x - cx)**2 + (points[vid].y - cy)**2) < bore_r_check
)

check_results.append({
    "check_name": "Bore Presence Check (vertices near Z-axis at bottom)",
    "measured": bore_verts_bottom,
    "expected": "> 0",
    "passed": bore_verts_bottom > 0,
    "unit": "vertex count",
    "reason": f"Vertices within r<{bore_r_check} mm of Z-axis at base: {bore_verts_bottom}. At top: {bore_verts_top}. >0 indicates bore inner wall geometry present."
})

# ═══════════════════════════════════════════════════════════════════
# CHECK D – Blade angular spacing (design: 7 blades → ~51.4° spacing)
# ═══════════════════════════════════════════════════════════════════
# Use the blade cluster data at mid-Z
z_sample_mid = cz_min + 30.0
frac_mid = 30.0 / 60.0
hub_r_mid = 50.0 - (50.0 - 15.0) * frac_mid
blade_r_thresh_mid = hub_r_mid + 3.0

blade_angles_mid = []
for vid in verts:
    p = points[vid]
    if abs(p.z - z_sample_mid) < 4.0:
        r = math.sqrt((p.x - cx)**2 + (p.y - cy)**2)
        if r > blade_r_thresh_mid:
            angle_deg = math.degrees(math.atan2(p.y - cy, p.x - cx)) % 360
            blade_angles_mid.append(angle_deg)

blade_angles_mid.sort()
clusters_mid = []
if blade_angles_mid:
    cur = [blade_angles_mid[0]]
    for a in blade_angles_mid[1:]:
        if a - cur[-1] > 15.0:
            clusters_mid.append(cur)
            cur = [a]
        else:
            cur.append(a)
    clusters_mid.append(cur)
    if len(clusters_mid) > 1 and (360 - clusters_mid[-1][-1] + clusters_mid[0][0]) < 15.0:
        clusters_mid[0] = clusters_mid[-1] + clusters_mid[0]
        clusters_mid = clusters_mid[:-1]

if len(clusters_mid) >= 2:
    centroids_mid = sorted([sum(c)/len(c) for c in clusters_mid])
    spacings = []
    for i in range(1, len(centroids_mid)):
        spacings.append(centroids_mid[i] - centroids_mid[i-1])
    # wrap-around
    spacings.append(360 - centroids_mid[-1] + centroids_mid[0])
    avg_spacing = sum(spacings) / len(spacings)
    spacing_note = f"{len(clusters_mid)} blades at mid-Z; avg spacing = {avg_spacing:.1f}°"
else:
    avg_spacing = 0.0
    spacing_note = f"Only {len(clusters_mid)} cluster(s) at mid-Z, cannot compute spacing"

expected_spacing = 360.0 / 7.0  # 51.43°
check_results.append({
    "check_name": "Blade Angular Spacing at Mid-Z (design: 360°/7 ≈ 51.4°)",
    "measured": round(avg_spacing, 2),
    "expected": round(expected_spacing, 2),
    "passed": abs(avg_spacing - expected_spacing) <= 15.0,
    "unit": "degrees",
    "reason": spacing_note + f" (expected ≈{expected_spacing:.1f}° ±15°)"
})
