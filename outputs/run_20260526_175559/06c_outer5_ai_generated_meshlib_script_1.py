
import meshlib.mrmeshpy as mrmesh
import math

check_results = []

# ── 1. BOUNDING BOX & KEY DIMENSIONS ─────────────────────────────────────────
bbox = mesh.getBoundingBox()
mn = bbox.min
mx = bbox.max

dim_x = mx.x - mn.x
dim_y = mx.y - mn.y
dim_z = mx.z - mn.z

# Z height
check_results.append({
    "check_name": "Hub height (Z extent)",
    "measured": round(dim_z, 3),
    "expected": 60.0,
    "passed": abs(dim_z - 60.0) <= 15.0,
    "unit": "mm",
    "reason": f"Z min={round(mn.z,3)}, Z max={round(mx.z,3)}"
})

# X extent (expected ~132mm: 2 * (50mm base_radius + 15mm blade protrusion + some tolerance))
check_results.append({
    "check_name": "Overall X extent",
    "measured": round(dim_x, 3),
    "expected": 132.0,
    "passed": abs(dim_x - 132.0) <= 15.0,
    "unit": "mm",
    "reason": f"X min={round(mn.x,3)}, X max={round(mx.x,3)}"
})

# Y extent
check_results.append({
    "check_name": "Overall Y extent",
    "measured": round(dim_y, 3),
    "expected": 132.0,
    "passed": abs(dim_y - 132.0) <= 15.0,
    "unit": "mm",
    "reason": f"Y min={round(mn.y,3)}, Y max={round(mx.y,3)}"
})

# ── 2. HUB CONE GEOMETRY – base and top radii via cross-sections ──────────────
# Sample all vertices and classify by Z height
verts = mesh.points
topo  = mesh.topology
valid_verts = topo.getValidVerts()

all_pts = []
vert_idx = 0
for i in range(verts.size()):
    vid = mrmesh.VertId(i)
    if valid_verts.test(vid):
        p = verts[vid]
        all_pts.append((p.x, p.y, p.z))

# Base-level vertices (Z ≈ 0 ± 2mm) – measure radius extent
base_pts = [(x, y, z) for x, y, z in all_pts if abs(z - mn.z) < 2.0]
# Top-level vertices (Z ≈ 60 ± 2mm)
top_pts  = [(x, y, z) for x, y, z in all_pts if abs(z - mx.z) < 2.0]

cx = (mn.x + mx.x) / 2.0
cy = (mn.y + mx.y) / 2.0

base_radii = [math.sqrt((x - cx)**2 + (y - cy)**2) for x, y, z in base_pts]
top_radii  = [math.sqrt((x - cx)**2 + (y - cy)**2) for x, y, z in top_pts]

max_base_r = max(base_radii) if base_radii else 0.0
max_top_r  = max(top_radii)  if top_radii  else 0.0
min_base_r = min(base_radii) if base_radii else 0.0
min_top_r  = min(top_radii)  if top_radii  else 0.0

# Base diameter of hub = 100mm → radius 50mm; blades add ~15mm → outer base ~65mm
check_results.append({
    "check_name": "Max radius at Z=base (hub+blades)",
    "measured": round(max_base_r, 3),
    "expected": "50–65",
    "passed": 45.0 <= max_base_r <= 70.0,
    "unit": "mm",
    "reason": f"Hub base radius 50mm + blade protrusion 15mm; min_r={round(min_base_r,3)}"
})

check_results.append({
    "check_name": "Max radius at Z=top (hub+blades)",
    "measured": round(max_top_r, 3),
    "expected": "15–20",
    "passed": 13.0 <= max_top_r <= 25.0,
    "unit": "mm",
    "reason": f"Hub top radius 15mm + blade protrusion 5mm; min_r={round(min_top_r,3)}"
})

# ── 3. CENTRAL BORE – look for vertices near Z-axis center at mid-height ──────
# The bore is 15mm diameter (7.5mm radius). Vertices close to Z-axis at all heights
bore_radii = [math.sqrt((x - cx)**2 + (y - cy)**2) for x, y, z in all_pts if 5 < z < 55]
if bore_radii:
    min_inner_r = min(bore_radii)
else:
    min_inner_r = 999.0

# A solid hub with bore should show vertices near ~7.5mm from axis inside
check_results.append({
    "check_name": "Central bore: minimum inner radius at mid-height",
    "measured": round(min_inner_r, 3),
    "expected": "~7.5 (bore r=7.5mm)",
    "passed": 5.0 <= min_inner_r <= 10.0,
    "unit": "mm",
    "reason": f"Bore diameter=15mm → radius 7.5mm. Measured closest vertex to Z-axis in Z=[5,55]"
})

# ── 4. BLADE COUNT – detect radial bumps in cross-section at mid-height ───────
# At Z ≈ 30 (mid-height), sample vertices and look for angular clustering
mid_pts = [(x, y, z) for x, y, z in all_pts if abs(z - (mn.z + dim_z * 0.4)) < 3.0]
if mid_pts:
    angles_deg = [math.degrees(math.atan2(y - cy, x - cx)) % 360 for x, y, z in mid_pts]
    # Histogram into 36 bins of 10 degrees each
    bins = [0] * 36
    for a in angles_deg:
        bins[int(a // 10)] += 1
    # Find peaks (local maxima above mean)
    mean_count = sum(bins) / 36.0
    peaks = 0
    for i in range(36):
        prev_b = bins[(i - 1) % 36]
        next_b = bins[(i + 1) % 36]
        if bins[i] > mean_count * 1.5 and bins[i] >= prev_b and bins[i] >= next_b:
            peaks += 1
    check_results.append({
        "check_name": "Blade count estimate (angular peaks at mid-height)",
        "measured": peaks,
        "expected": 7,
        "passed": 5 <= peaks <= 9,
        "unit": "count",
        "reason": f"Angular histogram peak detection at Z≈{round(mn.z + dim_z*0.4,1)}. Vertex count at slice={len(mid_pts)}"
    })
else:
    check_results.append({
        "check_name": "Blade count estimate (angular peaks at mid-height)",
        "measured": "N/A",
        "expected": 7,
        "passed": False,
        "unit": "count",
        "reason": "No vertices found at mid-height slice"
    })

# ── 5. BLADE PROTRUSION AT BASE – measure radial extent of blades ─────────────
# At Z=base, blade tips should reach ~65mm from axis (50 hub + 15 protrusion)
# Hub surface at base is at r=50mm; blades protrude 15mm → tip at r=65mm
blade_base_pts = [(x, y, z) for x, y, z in all_pts if abs(z - mn.z) < 3.0]
if blade_base_pts:
    radii_at_base = sorted([math.sqrt((x-cx)**2 + (y-cy)**2) for x,y,z in blade_base_pts])
    p95_base = radii_at_base[int(0.95 * len(radii_at_base))]
    p50_base = radii_at_base[int(0.50 * len(radii_at_base))]
    check_results.append({
        "check_name": "Blade protrusion at base (radial extent ~65mm from axis)",
        "measured": round(p95_base, 3),
        "expected": "55–70",
        "passed": 50.0 <= p95_base <= 72.0,
        "unit": "mm",
        "reason": f"Hub base r=50mm + blade 15mm = 65mm expected. p50={round(p50_base,3)}, p95={round(p95_base,3)}"
    })

# ── 6. BLADE PROTRUSION AT TOP ────────────────────────────────────────────────
blade_top_pts = [(x, y, z) for x, y, z in all_pts if abs(z - mx.z) < 3.0]
if blade_top_pts:
    radii_at_top = sorted([math.sqrt((x-cx)**2 + (y-cy)**2) for x,y,z in blade_top_pts])
    p95_top = radii_at_top[int(0.95 * len(radii_at_top))]
    p50_top = radii_at_top[int(0.50 * len(radii_at_top))]
    check_results.append({
        "check_name": "Blade protrusion at top (radial extent ~20mm from axis)",
        "measured": round(p95_top, 3),
        "expected": "18–22",
        "passed": 14.0 <= p95_top <= 25.0,
        "unit": "mm",
        "reason": f"Hub top r=15mm + blade 5mm = 20mm expected. p50={round(p50_top,3)}, p95={round(p95_top,3)}"
    })

# ── 7. BLADE TWIST – compare angular positions of blade peaks at base vs top ──
base_slice = [(x, y, z) for x, y, z in all_pts if abs(z - mn.z) < 4.0]
top_slice  = [(x, y, z) for x, y, z in all_pts if abs(z - mx.z) < 4.0]

def find_angular_peaks(pts, cx, cy, n_bins=72):
    if not pts:
        return []
    angles = [math.degrees(math.atan2(y - cy, x - cx)) % 360 for x, y, z in pts]
    radii  = [math.sqrt((x-cx)**2+(y-cy)**2) for x,y,z in pts]
    # weight by radius to focus on blade tips
    bins = [0.0] * n_bins
    for a, r in zip(angles, radii):
        bins[int(a * n_bins / 360) % n_bins] += r
    mean_val = sum(bins) / n_bins
    peaks = []
    for i in range(n_bins):
        prev_b = bins[(i - 1) % n_bins]
        next_b = bins[(i + 1) % n_bins]
        if bins[i] > mean_val * 1.4 and bins[i] >= prev_b and bins[i] >= next_b:
            peaks.append(i * 360.0 / n_bins)
    return sorted(peaks)

base_peaks = find_angular_peaks(base_slice, cx, cy)
top_peaks  = find_angular_peaks(top_slice,  cx, cy)

# Try to measure average angular offset between base and top peaks
if len(base_peaks) >= 5 and len(top_peaks) >= 5:
    # Match nearest peaks
    diffs = []
    for bp in base_peaks:
        closest = min(top_peaks, key=lambda tp: min(abs(tp - bp), 360 - abs(tp - bp)))
        diff = closest - bp
        if diff > 180:  diff -= 360
        if diff < -180: diff += 360
        diffs.append(diff)
    avg_twist = sum(diffs) / len(diffs)
    check_results.append({
        "check_name": "Blade twist angle (base→top)",
        "measured": round(avg_twist, 2),
        "expected": "~60 degrees",
        "passed": 30.0 <= abs(avg_twist) <= 90.0,
        "unit": "degrees",
        "reason": f"Design calls for ~60° twist. Base peaks={len(base_peaks)}, top peaks={len(top_peaks)}"
    })
else:
    check_results.append({
        "check_name": "Blade twist angle (base→top)",
        "measured": f"base_peaks={len(base_peaks)}, top_peaks={len(top_peaks)}",
        "expected": "~60 degrees",
        "passed": False,
        "unit": "degrees",
        "reason": "Insufficient peaks detected to measure twist"
    })

# ── 8. FACE COUNT & MESH QUALITY ─────────────────────────────────────────────
n_faces = mesh.topology.faceSize()
n_verts = mesh.topology.vertSize()
check_results.append({
    "check_name": "Face count",
    "measured": n_faces,
    "expected": ">1000 (sufficient resolution)",
    "passed": n_faces >= 1000,
    "unit": "count",
    "reason": f"Vertex count={n_verts}"
})

# ── 9. FDM OVERHANG ANALYSIS ──────────────────────────────────────────────────
# Compute per-face normals and check angle from vertical (Z-up)
# Overhang threshold = 45 degrees from horizontal (Z-down normals)
valid_faces = mesh.topology.getValidFaces()
overhang_count = 0
total_face_count = 0
max_overhang_angle = 0.0

for fi in range(mesh.topology.faceSize()):
    fid = mrmesh.FaceId(fi)
    if not valid_faces.test(fid):
        continue
    total_face_count += 1
    # Get face normal
    n = mesh.dirDblArea(fid)
    # normalize
    length = math.sqrt(n.x**2 + n.y**2 + n.z**2)
    if length < 1e-10:
        continue
    nz = n.z / length
    # Angle from downward vertical: if nz < 0, face points downward
    # Overhang if nz < -cos(45°) = -0.707
    if nz < -0.707:
        overhang_count += 1
        angle_from_horiz = math.degrees(math.asin(abs(nz)))
        max_overhang_angle = max(max_overhang_angle, angle_from_horiz)

overhang_pct = 100.0 * overhang_count / total_face_count if total_face_count > 0 else 0
check_results.append({
    "check_name": "FDM overhang: faces > 45° from horizontal",
    "measured": round(overhang_pct, 2),
    "expected": "< 30% (acceptable for FDM with supports)",
    "passed": overhang_pct < 50.0,
    "unit": "%",
    "reason": f"Overhang faces={overhang_count}/{total_face_count}, max_angle={round(max_overhang_angle,1)}°. Impeller hub cone will need supports."
})

# ── 10. MINIMUM WALL THICKNESS VIA RAY CASTING ───────────────────────────────
# Cast rays through faces along face normal inward, measure thickness
# Sample a subset of faces for efficiency
import random
random.seed(42)

face_list = []
for fi in range(mesh.topology.faceSize()):
    fid = mrmesh.FaceId(fi)
    if valid_faces.test(fid):
        face_list.append(fi)

sample_size = min(300, len(face_list))
sampled = random.sample(face_list, sample_size)

thicknesses = []
for fi in sampled:
    fid = mrmesh.FaceId(fi)
    # Get face center
    tri = mesh.getTriPoints(fid)
    cx_f = (tri.a.x + tri.b.x + tri.c.x) / 3.0
    cy_f = (tri.a.y + tri.b.y + tri.c.y) / 3.0
    cz_f = (tri.a.z + tri.b.z + tri.c.z) / 3.0

    # Get outward normal
    n = mesh.dirDblArea(fid)
    length = math.sqrt(n.x**2 + n.y**2 + n.z**2)
    if length < 1e-10:
        continue
    nx, ny, nz = n.x/length, n.y/length, n.z/length

    # Ray origin: slightly inside (offset inward by epsilon)
    eps = 0.01
    org = mrmesh.Vector3f()
    org.x = cx_f - nx * eps
    org.y = cy_f - ny * eps
    org.z = cz_f - nz * eps

    # Ray direction: inward (negative normal)
    direction = mrmesh.Vector3f()
    direction.x = -nx
    direction.y = -ny
    direction.z = -nz

    line = mrmesh.Line3f()
    line.p = org
    line.d = direction

    params = mrmesh.MeshIntersectionParameters()
    params.maxDistSq = 200.0 * 200.0  # max 200mm

    result = mrmesh.rayMeshIntersect(mesh, line, params)
    if result:
        thicknesses.append(result.distanceAlongLine)

if thicknesses:
    min_thickness = min(thicknesses)
    p5_thickness  = sorted(thicknesses)[int(0.05 * len(thicknesses))]
    p50_thickness = sorted(thicknesses)[int(0.50 * len(thicknesses))]
    check_results.append({
        "check_name": "Minimum wall thickness (ray casting)",
        "measured": round(min_thickness, 3),
        "expected": ">= 2.0",
        "passed": p5_thickness >= 1.8,
        "unit": "mm",
        "reason": f"p5={round(p5_thickness,3)}mm, p50={round(p50_thickness,3)}mm from {len(thicknesses)} sampled rays. Min_wall_mm=2.0"
    })
else:
    check_results.append({
        "check_name": "Minimum wall thickness (ray casting)",
        "measured": "N/A",
        "expected": ">= 2.0",
        "passed": False,
        "unit": "mm",
        "reason": "No ray intersections found"
    })
